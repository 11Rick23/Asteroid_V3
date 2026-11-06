"""順位はDBで計算・ページングする。表示UIは持たない。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import (
    PeriodChannel,
    PeriodChannelUser,
    PeriodRow,
    PeriodUser,
    RankingRevision,
    RankingRow,
)
from app.features.leveling.domain.numbers import amount, identifier, integer

from .dto import RankingEntry, RankingPage


class RankingRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def page(
        self,
        period_id: int,
        *,
        scope: str = "user",
        metric: str = "total",
        channel_id: int = 0,
        revision: int | None = None,
        offset: int = 0,
        limit: int = 10,
        top_rank: int | None = None,
    ) -> RankingPage | None:
        identifier(period_id)
        integer(offset)
        integer(limit, minimum=1, maximum=100)
        if revision is not None:
            identifier(revision)
        if top_rank is not None:
            identifier(top_rank)
        if scope not in ("user", "channel", "channel_user") or metric not in ("total", "text", "voice", "action"):
            raise ValueError("順位の対象・指標が不正です")
        if scope != "user" and metric not in ("text", "voice"):
            raise ValueError("チャンネル順位はtext/voiceのみです")
        if scope == "channel_user":
            identifier(channel_id)
        elif channel_id != 0:
            raise ValueError("全体順位のchannelキーは0です")
        async with self.sessions() as session:
            # READ COMMITTEDでも状態・count・pageの途中で公開/回収が割り込まない。
            period = (
                await session.scalars(
                    select(PeriodRow).where(PeriodRow.period_id == period_id).with_for_update(read=True)
                )
            ).one_or_none()
            if period is None:
                return None
            if period.status == "FINALIZED":
                selected_revision = revision if revision is not None else period.current_revision
                if await session.get(RankingRevision, (period_id, selected_revision)) is None:
                    raise ValueError("指定revisionが存在しません")
                ranked = (
                    select(
                        RankingRow.subject_id.label("subject_id"),
                        RankingRow.score.label("score"),
                        RankingRow.rank.label("rank"),
                    )
                    .where(
                        RankingRow.period_id == period_id,
                        RankingRow.revision == selected_revision,
                        RankingRow.scope == scope,
                        RankingRow.metric == metric,
                        RankingRow.channel_key == channel_id,
                    )
                    .subquery()
                )
            else:
                if revision is not None:
                    raise ValueError("OPEN期間にrevisionは指定できません")
                selected_revision = 0
                if scope == "user":
                    score = {
                        "total": PeriodUser.total_power,
                        "text": PeriodUser.text_power,
                        "voice": PeriodUser.voice_power,
                        "action": PeriodUser.action_power,
                    }[metric]
                    candidates = (
                        select(PeriodUser.user_id.label("subject_id"), score.label("score"))
                        .where(
                            PeriodUser.period_id == period_id,
                            score > 0,
                        )
                        .subquery()
                    )
                elif scope == "channel":
                    candidates = (
                        select(PeriodChannel.channel_id.label("subject_id"), PeriodChannel.power.label("score"))
                        .where(
                            PeriodChannel.period_id == period_id,
                            PeriodChannel.kind == metric,
                            PeriodChannel.power > 0,
                        )
                        .subquery()
                    )
                else:
                    candidates = (
                        select(PeriodChannelUser.user_id.label("subject_id"), PeriodChannelUser.power.label("score"))
                        .where(
                            PeriodChannelUser.period_id == period_id,
                            PeriodChannelUser.kind == metric,
                            PeriodChannelUser.channel_id == channel_id,
                            PeriodChannelUser.power > 0,
                        )
                        .subquery()
                    )
                ranked = select(
                    candidates.c.subject_id,
                    candidates.c.score,
                    func.rank().over(order_by=candidates.c.score.desc()).label("rank"),
                ).subquery()
            query = select(ranked)
            if top_rank is not None:
                query = query.where(ranked.c.rank <= top_rank)
            filtered = query.subquery()
            count = await session.scalar(select(func.count()).select_from(filtered))
            rows = await session.execute(
                select(filtered).order_by(filtered.c.rank, filtered.c.subject_id).offset(offset).limit(limit)
            )
            entries = tuple(
                RankingEntry(identifier(row.subject_id), amount(row.score), identifier(int(row.rank))) for row in rows
            )
            return RankingPage(period_id, selected_revision, entries, int(count or 0))

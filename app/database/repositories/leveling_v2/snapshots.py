"""確定版の正本入力と派生順位。イベント履歴からの再計算は行わない。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import (
    PeriodChannelUser,
    PeriodUser,
    RankingRevision,
    RankingRow,
    SnapshotChannelInput,
    SnapshotUserInput,
)
from app.features.leveling.domain.numbers import amount, identifier, total_amount
from app.features.leveling.domain.rankings import rank_scores

from .dto import RevisionResult

type UserInputs = dict[int, tuple[int, int, int]]
type ChannelInputs = dict[tuple[int, str, int], int]
type Scores = dict[tuple[str, str, int], dict[int, int]]


@dataclass
class SnapshotInputs:
    users: UserInputs
    channels: ChannelInputs

    def scores(self) -> Scores:
        result: Scores = {}

        def add(scope: str, metric: str, channel: int, subject: int, value: int) -> None:
            identifier(subject)
            amount(value)
            if value:
                bucket = result.setdefault((scope, metric, channel), {})
                bucket[subject] = total_amount(bucket.get(subject, 0), value)

        for user, values in self.users.items():
            for metric, value in zip(("text", "voice", "action"), values, strict=True):
                add("user", metric, 0, user, value)
                add("user", "total", 0, user, value)
        for (channel, kind, user), value in self.channels.items():
            identifier(channel)
            if kind not in ("text", "voice"):
                raise ValueError("チャンネル種別が不正です")
            add("user", kind, 0, user, value)
            add("user", "total", 0, user, value)
            add("channel", kind, 0, channel, value)
            add("channel_user", kind, channel, user, value)
        return result


async def open_inputs(session: AsyncSession, period_id: int, *, lock: bool = True) -> SnapshotInputs:
    user_query = select(PeriodUser).where(PeriodUser.period_id == period_id).order_by(PeriodUser.user_id)
    channel_query = (
        select(PeriodChannelUser)
        .where(PeriodChannelUser.period_id == period_id)
        .order_by(
            PeriodChannelUser.channel_id,
            PeriodChannelUser.kind,
            PeriodChannelUser.user_id,
        )
    )
    if lock:
        user_query = user_query.with_for_update()
        channel_query = channel_query.with_for_update()
    users = {
        row.user_id: (row.unallocated_text, row.unallocated_voice, row.action_power)
        for row in await session.scalars(user_query)
        if row.unallocated_text or row.unallocated_voice or row.action_power
    }
    channels = {
        (row.channel_id, row.kind, row.user_id): row.power for row in await session.scalars(channel_query) if row.power
    }
    return SnapshotInputs(users, channels)


async def revision_inputs(session: AsyncSession, period_id: int, revision: int) -> SnapshotInputs:
    users = {
        row.user_id: (row.unallocated_text, row.unallocated_voice, row.action_power)
        for row in await session.scalars(
            select(SnapshotUserInput)
            .where(
                SnapshotUserInput.period_id == period_id,
                SnapshotUserInput.revision == revision,
            )
            .order_by(SnapshotUserInput.user_id)
            .with_for_update(read=True)
        )
    }
    channels = {
        (row.channel_id, row.kind, row.user_id): row.power
        for row in await session.scalars(
            select(SnapshotChannelInput)
            .where(
                SnapshotChannelInput.period_id == period_id,
                SnapshotChannelInput.revision == revision,
            )
            .order_by(SnapshotChannelInput.channel_id, SnapshotChannelInput.kind, SnapshotChannelInput.user_id)
            .with_for_update(read=True)
        )
    }
    return SnapshotInputs(users, channels)


def snapshot_content(inputs: SnapshotInputs) -> tuple[list[tuple[str, str, int, int, int, int]], int, str]:
    rankings = [
        (scope, metric, channel, row.subject_id, row.score, row.rank)
        for (scope, metric, channel), scores in sorted(inputs.scores().items())
        for row in rank_scores(scores)
    ]
    # JSON数値の消費側精度に依存しない正規化十進表現。全行順を固定する。
    content = {
        "users": [[str(user), *(str(v) for v in values)] for user, values in sorted(inputs.users.items())],
        "channels": [[str(c), k, str(u), str(v)] for (c, k, u), v in sorted(inputs.channels.items())],
        "rankings": [[scope, metric, str(c), str(u), str(v), str(r)] for scope, metric, c, u, v, r in rankings],
    }
    checksum = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    count = len(inputs.users) + len(inputs.channels) + len(rankings)
    return rankings, count, checksum


async def save_revision(
    session: AsyncSession,
    period_id: int,
    revision: int,
    inputs: SnapshotInputs,
    now: datetime,
    *,
    correction_id: int | None = None,
) -> RevisionResult:
    """新しい版へINSERTのみ。旧版のUPDATE・DELETEは行わない。"""
    rankings, count, checksum = snapshot_content(inputs)
    session.add(
        RankingRevision(
            period_id=period_id,
            revision=revision,
            created_at=now,
            source="close" if correction_id is None else "correction",
            correction_id=correction_id,
            row_count=count,
            checksum=checksum,
        )
    )
    await session.flush()
    session.add_all(
        SnapshotUserInput(
            period_id=period_id,
            revision=revision,
            user_id=user,
            unallocated_text=values[0],
            unallocated_voice=values[1],
            action_power=values[2],
        )
        for user, values in sorted(inputs.users.items())
    )
    session.add_all(
        SnapshotChannelInput(
            period_id=period_id,
            revision=revision,
            channel_id=channel,
            kind=kind,
            user_id=user,
            power=power,
        )
        for (channel, kind, user), power in sorted(inputs.channels.items())
    )
    session.add_all(
        RankingRow(
            period_id=period_id,
            revision=revision,
            scope=scope,
            metric=metric,
            channel_key=channel,
            subject_id=subject,
            score=score,
            rank=rank,
        )
        for scope, metric, channel, subject, score, rank in rankings
    )
    await session.flush()
    return RevisionResult(period_id, revision, count, checksum)


async def verify_revision(session: AsyncSession, period_id: int, revision: int) -> RevisionResult:
    row = (
        await session.scalars(
            select(RankingRevision)
            .where(
                RankingRevision.period_id == period_id,
                RankingRevision.revision == revision,
            )
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise ValueError("公開revisionが存在しません")
    inputs = await revision_inputs(session, period_id, revision)
    expected, count, checksum = snapshot_content(inputs)
    actual = [
        (r.scope, r.metric, r.channel_key, r.subject_id, r.score, r.rank)
        for r in await session.scalars(
            select(RankingRow)
            .where(
                RankingRow.period_id == period_id,
                RankingRow.revision == revision,
            )
            .order_by(RankingRow.scope, RankingRow.metric, RankingRow.channel_key, RankingRow.subject_id)
            .with_for_update(read=True)
        )
    ]
    if sorted(actual) != sorted(expected) or row.row_count != count or row.checksum != checksum:
        raise ValueError("公開revisionの件数・checksum・派生順位が一致しません")
    return RevisionResult(period_id, revision, count, checksum)

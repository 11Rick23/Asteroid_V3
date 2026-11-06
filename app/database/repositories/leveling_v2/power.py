from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import PeriodChannel, PeriodChannelUser, PeriodRow, PeriodUser
from app.features.leveling.domain.numbers import amount, total_amount

from .storage import ensure


async def add_power(
    session: AsyncSession,
    periods: list[PeriodRow],
    user_id: int,
    kind: str,
    power: int,
    channels: tuple[tuple[int, int], ...],
) -> None:
    amount(power)
    if kind not in ("text", "voice", "action"):
        raise ValueError("パワー種別が不正です")
    if len({c for c, _ in channels}) != len(channels):
        raise ValueError("チャンネル割当が重複しています")
    allocated = total_amount(*(value for _, value in channels))
    if allocated > power or (kind == "action" and channels):
        raise ValueError("チャンネル割当が不正です")
    accepted = [p for p in periods if p.status == "OPEN"]
    # periodロック済み。入力/集計表を表順・PK順で更新する。
    for period in sorted(accepted, key=lambda p: p.period_id):
        await ensure(session, PeriodUser, {"period_id": period.period_id, "user_id": user_id}, "user_id")
        row = (
            await session.scalars(
                select(PeriodUser)
                .where(PeriodUser.period_id == period.period_id, PeriodUser.user_id == user_id)
                .with_for_update()
            )
        ).one()
        if kind == "text":
            row.text_power = total_amount(row.text_power, power)
            row.unallocated_text = total_amount(row.unallocated_text, power - allocated)
        elif kind == "voice":
            row.voice_power = total_amount(row.voice_power, power)
            row.unallocated_voice = total_amount(row.unallocated_voice, power - allocated)
        else:
            row.action_power = total_amount(row.action_power, power)
        row.total_power = total_amount(row.text_power, row.voice_power, row.action_power)
    for model in (PeriodChannelUser, PeriodChannel):
        for period in sorted(accepted, key=lambda p: p.period_id):
            for channel_id, value in sorted(channels):
                keys = {"period_id": period.period_id, "channel_id": channel_id, "kind": kind}
                if model is PeriodChannelUser:
                    keys["user_id"] = user_id
                await ensure(session, model, keys, "channel_id")
                query = select(model).filter_by(**keys).with_for_update()
                row = (await session.scalars(query)).one()
                row.power = total_amount(row.power, value)

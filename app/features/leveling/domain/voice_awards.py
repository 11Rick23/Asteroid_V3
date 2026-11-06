from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from .allocation import allocate_power
from .boosts import ShardAward
from .numbers import amount, coefficient
from .periods import PeriodKind
from .voice_limits import VoiceLimits, cap_voice_award
from .voice_time import UNIT_US, VoiceUnit


@dataclass(frozen=True)
class VoiceAward:
    shard: ShardAward
    power: int
    channel_power: tuple[tuple[int, int], ...]
    period_power: tuple[tuple[PeriodKind, int], ...]
    next_limits: VoiceLimits


def calculate_voice_award(
    unit: VoiceUnit,
    raw_xp: int,
    limits: VoiceLimits,
    accepted_periods: frozenset[PeriodKind],
    *,
    adjustment: Decimal = Decimal("0.3"),
) -> VoiceAward:
    """固定済み60秒乱数を時間比例し、最後のfloor後に独立上限を適用する。"""
    amount(raw_xp)
    scale = raw_xp * coefficient(adjustment) / UNIT_US
    shard_us = sum(part.duration for part in unit.segments if part.shard_eligible)
    weighted_us = sum(
        (Fraction(part.duration * (100 + part.rate_percent), 100) for part in unit.segments if part.shard_eligible),
        Fraction(0),
    )
    base = int(scale * shard_us)
    total = int(scale * weighted_us)
    durations: dict[int, int] = {}
    for part in unit.segments:
        if part.power_eligible:
            durations[part.channel_id] = durations.get(part.channel_id, 0) + part.duration
    power = amount(int(scale * sum(durations.values())))
    # clipで範囲超過を隠さない。中間積は任意精度、付与候補整数は格納範囲を検査。
    capped = cap_voice_award(ShardAward(base, total - base), power, limits, accepted_periods)
    return VoiceAward(
        capped.shard,
        capped.power,
        tuple(allocate_power(capped.power, durations).items()),
        tuple((kind, capped.power if kind in accepted_periods else 0) for kind in PeriodKind),
        capped.next_limits,
    )

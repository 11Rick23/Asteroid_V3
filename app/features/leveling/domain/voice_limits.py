from __future__ import annotations

from dataclasses import dataclass

from .boosts import ShardAward
from .numbers import amount, total_amount
from .periods import PeriodKind


@dataclass(frozen=True)
class VoiceLimits:
    pending_shard: int = 0
    pending_power: int = 0
    shard_limit: int = 300
    power_limit: int = 300

    def __post_init__(self) -> None:
        for value in (self.pending_shard, self.pending_power, self.shard_limit, self.power_limit):
            amount(value)
        if not self.shard_limit or not self.power_limit:
            raise ValueError("未受取上限は正の整数で指定してください")

    @property
    def shard_room(self) -> int:
        return max(0, self.shard_limit - self.pending_shard)

    @property
    def power_room(self) -> int:
        return max(0, self.power_limit - self.pending_power)


@dataclass(frozen=True)
class CappedVoiceAward:
    shard: ShardAward
    power: int
    next_limits: VoiceLimits


def cap_voice_award(
    shard: ShardAward, power: int, limits: VoiceLimits, accepted_periods: frozenset[PeriodKind]
) -> CappedVoiceAward:
    """DR06: 全期間不受理でもシャードを付与し、power meterは消費しない。"""
    amount(power)
    if any(not isinstance(kind, PeriodKind) for kind in accepted_periods):
        raise ValueError("受理期間種別が不正です")
    base = min(shard.base, limits.shard_room)
    bonus = min(shard.bonus, limits.shard_room - base)
    accepted_power = min(power, limits.power_room) if accepted_periods else 0
    return CappedVoiceAward(
        ShardAward(base, bonus),
        accepted_power,
        VoiceLimits(
            total_amount(limits.pending_shard, base, bonus),
            total_amount(limits.pending_power, accepted_power),
            limits.shard_limit,
            limits.power_limit,
        ),
    )

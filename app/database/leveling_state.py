from __future__ import annotations

from dataclasses import dataclass

from app.features.leveling.domain.math_calculation import PRESTIGE_REQUIRED_SHARD, calculation_shard

MAX_POWER = 2**32 - 1
MAX_TOTAL_SHARD = 256 * PRESTIGE_REQUIRED_SHARD - 1


@dataclass(frozen=True, slots=True)
class ShardState:
    text: int = 0
    voice: int = 0
    bonus: int = 0

    def validate(self) -> None:
        if min(self.text, self.voice, self.bonus) < 0 or self.total > MAX_TOTAL_SHARD:
            raise ValueError("shard_out_of_range")

    @property
    def total(self) -> int:
        return self.text + self.voice + self.bonus

    def progression(self) -> tuple[int, int, int]:
        self.validate()
        return calculation_shard(0, 0, 0, self.total)[:3]


@dataclass(frozen=True, slots=True)
class PowerState:
    text: int = 0
    voice: int = 0
    action: int = 0

    def validate(self) -> None:
        if min(self.text, self.voice, self.action) < 0 or max(self.text, self.voice, self.action) > MAX_POWER:
            raise ValueError("power_out_of_range")

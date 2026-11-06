from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.features.leveling.domain.numbers import amount, coefficient, identifier, integer
from app.features.leveling.domain.periods import aware


@dataclass(frozen=True)
class VoiceSettlement:
    user_id: int
    expected_version: int
    measurement_epoch: str
    grant_seq: int
    through: datetime
    recorded_at: datetime
    next_random: int | None = None
    shard_limit: int = 300
    power_limit: int = 300
    adjustment: Decimal = Decimal("0.3")

    def __post_init__(self) -> None:
        identifier(self.user_id)
        identifier(self.grant_seq)
        integer(self.expected_version, maximum=2**64 - 2)
        if not self.measurement_epoch or len(self.measurement_epoch) > 64:
            raise ValueError("計測epochが不正です")
        aware(self.through)
        aware(self.recorded_at)
        if self.recorded_at < self.through:
            raise ValueError("記録時刻より未来を精算できません")
        if self.next_random is not None:
            amount(self.next_random)
        if not amount(self.shard_limit) or not amount(self.power_limit):
            raise ValueError("未受取上限は正の整数で指定してください")
        coefficient(self.adjustment)

    @property
    def operation_key(self) -> str:
        return f"voice:{self.user_id}:{self.measurement_epoch}:{self.grant_seq}"

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.database.leveling_state import MAX_POWER, PowerState, ShardState


@dataclass(frozen=True, slots=True)
class MigrationOptions:
    leveling: bool = True
    roles: bool = True
    birthday: bool = True
    free_category: bool = True


@dataclass(frozen=True, slots=True)
class PendingState:
    voice_shard: int = 0
    bonus_shard: int = 0
    voice_power: int = 0
    half_notify: bool = False
    full_notify: bool = False

    def validate(self) -> None:
        if not all(0 <= value <= MAX_POWER for value in (self.voice_shard, self.bonus_shard, self.voice_power)):
            raise ValueError("pending_out_of_range")


@dataclass(frozen=True, slots=True)
class AccountState:
    user_id: int
    shards: ShardState = ShardState()
    powers: PowerState = PowerState()
    pending: PendingState = PendingState()
    birthday: date | None = None
    saved_roles: tuple[int, ...] = ()


def merge_leveling(source: AccountState, target: AccountState) -> tuple[ShardState, PowerState, PendingState]:
    shards = ShardState(
        source.shards.text + target.shards.text,
        source.shards.voice + target.shards.voice,
        source.shards.bonus + target.shards.bonus,
    )
    powers = PowerState(
        source.powers.text + target.powers.text,
        source.powers.voice + target.powers.voice,
        source.powers.action + target.powers.action,
    )
    pending = PendingState(
        source.pending.voice_shard + target.pending.voice_shard,
        source.pending.bonus_shard + target.pending.bonus_shard,
        source.pending.voice_power + target.pending.voice_power,
        source.pending.half_notify or target.pending.half_notify,
        source.pending.full_notify or target.pending.full_notify,
    )
    shards.validate()
    powers.validate()
    pending.validate()
    # 未受取分を受け取った後もDBの上限内に収まること。
    ShardState(shards.text, shards.voice + pending.voice_shard, shards.bonus + pending.bonus_shard).validate()
    PowerState(powers.text, powers.voice + pending.voice_power, powers.action).validate()
    return shards, powers, pending

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.features.leveling.domain.growth import Growth
from app.features.leveling.domain.periods import Period
from app.features.leveling.domain.voice_time import VoiceSegment


@dataclass(frozen=True)
class AccountData:
    user_id: int
    text_shard: int
    voice_shard: int
    bonus_shard: int
    growth: Growth
    version: int


@dataclass(frozen=True)
class PeriodData:
    period_id: int
    period: Period
    status: str
    current_revision: int


@dataclass(frozen=True)
class AwardResult:
    operation_key: str
    event_id: int
    user_id: int
    base_shard: int
    bonus_shard: int
    power: int
    accepted_period_ids: tuple[int, ...]
    rejected_period_ids: tuple[int, ...]


@dataclass(frozen=True)
class ClaimResult:
    claim_id: int
    operation_key: str
    user_id: int
    voice_shard: int
    bonus_shard: int
    power_released: int


@dataclass(frozen=True)
class VoiceStateData:
    user_id: int
    measurement_epoch: str
    state: str
    last_channel_id: int | None
    last_confirmed_at: datetime
    checkpoint_version: int
    next_grant_seq: int
    prepared_grant_seq: int | None
    prepared_random: int | None
    calculation_version: str
    consumed_segment_seq: int
    consumed_offset_us: int
    eligible_elapsed_us: int
    pending_cycle: int
    cap_notice_attempted: bool
    segments: tuple[VoiceSegment, ...]


@dataclass(frozen=True)
class RankingEntry:
    subject_id: int
    score: int
    rank: int


@dataclass(frozen=True)
class RankingPage:
    period_id: int
    revision: int
    entries: tuple[RankingEntry, ...]
    count: int


@dataclass(frozen=True)
class RevisionResult:
    period_id: int
    revision: int
    row_count: int
    checksum: str


@dataclass(frozen=True)
class OutboxData:
    job_id: int
    dedupe_key: str
    type: str
    payload: dict[str, object]
    state: str
    attempt_count: int
    lease_token: str | None

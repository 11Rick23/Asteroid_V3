"""既知の有効区間だけを消費する。時計・接続状態・乱数は参照しない。"""

from __future__ import annotations

from collections.abc import Sequence, Set
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .boosts import Boost, rate_at, validate_boosts
from .numbers import MAX_DURATION_US, boolean, identifier, integer
from .periods import Period, aware, duration_us, next_boundary, periods_at

UNIT_US = 60_000_000


@dataclass(frozen=True)
class VoiceMember:
    user_id: int
    bot: bool = False
    self_mute: bool = False
    self_deaf: bool = False
    server_mute: bool = False
    server_deaf: bool = False
    afk: bool = False
    excluded_role: bool = False

    def __post_init__(self) -> None:
        identifier(self.user_id)
        for value in (
            self.bot,
            self.self_mute,
            self.self_deaf,
            self.server_mute,
            self.server_deaf,
            self.afk,
            self.excluded_role,
        ):
            boolean(value)

    @property
    def counts(self) -> bool:
        return not (self.bot or self.self_mute or self.self_deaf or self.server_mute or self.server_deaf or self.afk)


def eligible_members(
    members: Sequence[VoiceMember], *, excluded_channel: bool = False, stage: bool = False
) -> frozenset[int]:
    boolean(excluded_channel)
    boolean(stage)
    if len({member.user_id for member in members}) != len(members):
        raise ValueError("参加者IDが重複しています")
    if excluded_channel or stage or sum(member.counts for member in members) < 2:
        return frozenset()
    return frozenset(member.user_id for member in members if member.counts and not member.excluded_role)


@dataclass(frozen=True)
class VoiceSegment:
    start: datetime
    end: datetime
    channel_id: int
    rate_percent: int = 0
    shard_eligible: bool = True
    power_eligible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", aware(self.start))
        object.__setattr__(self, "end", aware(self.end))
        integer(self.duration, minimum=1, maximum=MAX_DURATION_US)
        identifier(self.channel_id)
        # 合算率は任意精度の中間値。予約単位の範囲検査はBoostが担当する。
        if type(self.rate_percent) is not int or self.rate_percent < 0:
            raise ValueError("加算率は非負整数で指定してください")
        boolean(self.shard_eligible)
        boolean(self.power_eligible)

    @property
    def duration(self) -> int:
        return duration_us(self.start, self.end)


def boosted_segments(
    start: datetime,
    end: datetime,
    channel_id: int,
    boosts: Sequence[Boost],
    role_ids: Set[int],
    *,
    shard_eligible: bool = True,
    power_eligible: bool = True,
) -> tuple[VoiceSegment, ...]:
    """ロール・資格が一定の既知区間を、予約の開始・終了・取消で分割する。"""
    start, end = aware(start), aware(end)
    validate_boosts(boosts)
    VoiceSegment(start, end, channel_id, 0, shard_eligible, power_eligible)
    cuts = {start, end}
    for boost in boosts:
        if boost.role_id in role_ids:
            cuts.update(
                at for at in (boost.start, boost.end, boost.cancelled_at) if at is not None and start < at < end
            )
    ordered = sorted(cuts)
    return tuple(
        VoiceSegment(left, right, channel_id, rate_at(boosts, role_ids, left), shard_eligible, power_eligible)
        for left, right in zip(ordered, ordered[1:], strict=False)
    )


def validate_segments(segments: Sequence[VoiceSegment]) -> None:
    for previous, current in zip(segments, segments[1:], strict=False):
        if previous.end > current.start:
            raise ValueError("VC区間は時系列順かつ非重複にしてください")


@dataclass(frozen=True)
class VoiceUnit:
    segments: tuple[VoiceSegment, ...]
    settled_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))
        object.__setattr__(self, "settled_at", aware(self.settled_at))
        if not self.segments:
            raise ValueError("空の付与単位は作成できません")
        validate_segments(self.segments)
        if any(not (part.shard_eligible or part.power_eligible) for part in self.segments):
            raise ValueError("両側停止区間を付与単位に含められません")
        integer(self.duration, minimum=1, maximum=UNIT_US)
        boundary = next_boundary(self.segments[0].start)
        if self.segments[-1].end > boundary or self.settled_at < self.segments[-1].end:
            raise ValueError("付与単位が期間境界または精算時刻を越えています")
        expected = self.segments[-1].end if self.duration == UNIT_US else boundary
        if self.settled_at != expected:
            raise ValueError("60秒未満は期間境界でのみ精算できます")

    @property
    def duration(self) -> int:
        return sum(segment.duration for segment in self.segments)

    @property
    def periods(self) -> tuple[Period, ...]:
        return periods_at(self.segments[0].start)


@dataclass(frozen=True)
class VoiceStep:
    unit: VoiceUnit | None
    remaining: tuple[VoiceSegment, ...]


def take_voice_unit(segments: Sequence[VoiceSegment], through: datetime) -> VoiceStep:
    """1単位だけ取り出す。残余を次回へ渡し、付与後に上限の資格を再評価する。

    throughは既知区間の処理期限。区間のない空白を有効時間として補わない。
    永続化側はunitとremainingを同一トランザクションで確定する。
    """
    through = aware(through)
    validate_segments(segments)
    if segments and through < segments[-1].end:
        raise ValueError("処理期限より未来の区間があります")
    pending = tuple(part for part in segments if part.shard_eligible or part.power_eligible)
    if not pending:
        return VoiceStep(None, ())
    boundary = next_boundary(pending[0].start)
    taken: list[VoiceSegment] = []
    elapsed = 0
    for index, part in enumerate(pending):
        if part.start >= boundary:
            return VoiceStep(VoiceUnit(tuple(taken), boundary), pending[index:])
        end = min(part.end, boundary, part.start + timedelta(microseconds=UNIT_US - elapsed))
        piece = replace(part, end=end)
        taken.append(piece)
        elapsed += piece.duration
        remainder = ((replace(part, start=end),) if end < part.end else ()) + pending[index + 1 :]
        if elapsed == UNIT_US or end == boundary:
            return VoiceStep(VoiceUnit(tuple(taken), end), remainder)
    if through >= boundary:
        return VoiceStep(VoiceUnit(tuple(taken), boundary), ())
    return VoiceStep(None, pending)

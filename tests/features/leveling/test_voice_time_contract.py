from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.features.leveling.domain.periods import JST
from app.features.leveling.domain.voice_time import (
    UNIT_US,
    VoiceMember,
    VoiceSegment,
    VoiceUnit,
    eligible_members,
    take_voice_unit,
)

START = datetime(2026, 10, 31, 12, tzinfo=JST)


@pytest.mark.parametrize("count,expected", [(1, frozenset()), (2, frozenset({1, 2})), (3, frozenset({1, 2, 3}))])
def test_participant_count(count: int, expected: frozenset[int]):
    """有効参加者が2人以上のときだけVC獲得を許可する。"""
    # 機能要件：現行の人数条件を維持する。
    # Given / When / Then
    assert eligible_members([VoiceMember(i) for i in range(1, count + 1)]) == expected


@pytest.mark.parametrize("flag", ["bot", "self_mute", "self_deaf", "server_mute", "server_deaf", "afk"])
def test_inactive_member(flag: str):
    """Bot・ミュート・聴覚無効・AFKの参加者は人数条件に数えない。"""
    # 機能要件：無効な参加者によって他者の獲得条件を満たさない。
    # Given
    members = [VoiceMember(1), replace(VoiceMember(2), **{flag: True})]
    # When / Then
    assert eligible_members(members) == frozenset()


def test_exclusions():
    """除外ロールの人は人数に含め、除外チャンネルとStageは全員停止する。"""
    # 機能要件：付与除外と人数判定を分離する。
    # Given
    members = [VoiceMember(1), VoiceMember(2, excluded_role=True)]
    # When / Then
    assert eligible_members(members) == {1}
    assert eligible_members(members, excluded_channel=True) == set()
    assert eligible_members(members, stage=True) == set()
    with pytest.raises(ValueError):
        eligible_members([members[0], members[0]])


@pytest.mark.parametrize("seconds", [1, 20, 59])
def test_carries_remainder(seconds: int):
    """60秒未満は保持し、退出による空白を足さず再参加後の有効時間と合算する。"""
    # 機能要件：退出やチェックポイントで既知端数を失わない。
    # Given
    first = VoiceSegment(START, START + timedelta(seconds=seconds), 1)
    # When
    step = take_voice_unit([first], first.end)
    second = VoiceSegment(START + timedelta(hours=1), START + timedelta(hours=1, seconds=60 - seconds), 2)
    complete = take_voice_unit((*step.remaining, second), second.end)
    # Then
    assert step.unit is None
    assert step.remaining == (first,)
    assert complete.unit is not None and complete.unit.duration == UNIT_US
    assert complete.remaining == ()
    assert take_voice_unit(complete.remaining, second.end).unit is None


@pytest.mark.parametrize(
    "boundary",
    [
        datetime(2026, 11, 2, tzinfo=JST),  # 日・週
        datetime(2027, 1, 1, tzinfo=JST),  # 日・月・年
        datetime(2027, 2, 1, tzinfo=JST),  # 日・週・月
        datetime(2024, 3, 1, tzinfo=JST),  # 閏日・月
    ],
)
@pytest.mark.parametrize("seconds", [20, 60])
def test_boundary_once(boundary: datetime, seconds: int):
    """日週月の同時境界と60秒一致でも精算は1件で、獲得は前期間に帰属する。"""
    # 非機能要件：期間境界で端数を二重消費しない。
    # Given
    segment = VoiceSegment(boundary - timedelta(seconds=seconds), boundary, 1)
    # When
    step = take_voice_unit([segment], boundary)
    # Then
    assert step.unit is not None
    assert step.unit.duration == seconds * 1_000_000
    assert all(p.contains(segment.start) for p in step.unit.periods)
    assert step.unit.periods[0].end == boundary
    assert step.remaining == ()
    assert take_voice_unit(step.remaining, boundary).unit is None


def test_crossing_and_recovery():
    """保存端数だけを旧日境界で精算し、復旧までの不明時間を計上しない。"""
    # 非機能要件：境界を跨ぐ停止時間は0秒として扱う。
    # Given
    boundary = datetime(2026, 11, 1, tzinfo=JST)
    old = VoiceSegment(boundary - timedelta(seconds=30), boundary - timedelta(seconds=10), 1)
    new = VoiceSegment(boundary + timedelta(days=2), boundary + timedelta(days=2, seconds=70), 2)
    # When
    first = take_voice_unit([old, new], new.end)
    second = take_voice_unit(first.remaining, new.end)
    # Then
    assert first.unit is not None and first.unit.duration == 20_000_000
    assert first.unit.settled_at == boundary
    assert second.unit is not None and second.unit.duration == UNIT_US
    assert second.remaining[0].duration == 10_000_000


def test_multiple_boundaries():
    """複数日を跨ぐ既知区間は順番に消費し、総有効時間が保存される。"""
    # 非機能要件：区間分割によって有効時間を重複・欠落させない。
    # Given
    boundary = datetime(2027, 2, 1, tzinfo=JST)
    segment = VoiceSegment(boundary - timedelta(seconds=20), boundary + timedelta(days=1, seconds=59), 1)
    remaining = (segment,)
    consumed = 0
    units = 0
    # When
    while True:
        step = take_voice_unit(remaining, segment.end)
        remaining = step.remaining
        if step.unit is None:
            break
        consumed += step.unit.duration
        units += 1
    # Then
    assert consumed + sum(part.duration for part in remaining) == segment.duration
    assert units == 1441
    assert sum(part.duration for part in remaining) == 59_000_000


def test_stopped_clock():
    """両側停止区間は付与時計を進めず、片側だけ有効なら時間を保持する。"""
    # 機能要件：独立上限により停止した側の時間を後付けで付与しない。
    # Given
    stopped = VoiceSegment(START, START + timedelta(seconds=30), 1, shard_eligible=False, power_eligible=False)
    active = VoiceSegment(stopped.end, stopped.end + timedelta(seconds=60), 1, shard_eligible=False)
    # When
    step = take_voice_unit([stopped, active], active.end)
    # Then
    assert step.unit is not None and step.unit.segments == (active,)
    assert take_voice_unit([stopped], stopped.end).remaining == ()


def test_invalid_intervals():
    """逆転・重複・期限超過・通常の60秒未満付与を拒否する。"""
    # 非機能要件：不正な時間や重複区間から付与単位を作らない。
    # Given
    part = VoiceSegment(START, START + timedelta(seconds=59), 1)
    # When / Then
    with pytest.raises(ValueError):
        VoiceSegment(START, START, 1)
    with pytest.raises(ValueError):
        take_voice_unit([part, part], part.end)
    with pytest.raises(ValueError):
        take_voice_unit([part], START)
    with pytest.raises(ValueError):
        VoiceUnit((part,), part.end)

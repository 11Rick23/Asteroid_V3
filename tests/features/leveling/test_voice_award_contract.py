from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from app.features.leveling.domain.allocation import allocate_power
from app.features.leveling.domain.boosts import Boost, ShardAward
from app.features.leveling.domain.numbers import MAX_AMOUNT
from app.features.leveling.domain.periods import JST, PeriodKind
from app.features.leveling.domain.voice_awards import calculate_voice_award
from app.features.leveling.domain.voice_limits import VoiceLimits, cap_voice_award
from app.features.leveling.domain.voice_time import VoiceSegment, VoiceUnit, boosted_segments, take_voice_unit

START = datetime(2026, 11, 1, 12, tzinfo=JST)
ALL_PERIODS = frozenset(PeriodKind)


def test_time_weighted_boost():
    """30秒0%と30秒100%では基本6・ボーナス3・パワー6を付与する。"""
    # 機能要件：調整係数と時間比例ブーストを最終段階で切り捨てる。
    # Given
    unit = VoiceUnit(
        (
            VoiceSegment(START, START + timedelta(seconds=30), 1),
            VoiceSegment(START + timedelta(seconds=30), START + timedelta(seconds=60), 2, 100),
        ),
        START + timedelta(seconds=60),
    )
    # When
    award = calculate_voice_award(unit, 20, VoiceLimits(), ALL_PERIODS)
    # Then
    assert award.shard == ShardAward(6, 3)
    assert award.power == 6
    assert dict(award.channel_power) == {1: 3, 2: 3}
    assert dict(award.period_power) == dict.fromkeys(PeriodKind, 6)


@pytest.mark.parametrize("chunk_us", [1_000_000, 10_000_000, 30_000_000, 60_000_000])
def test_checkpoint_independent(chunk_us: int):
    """チェックポイントを細かくしても途中の切り捨てや再付与は発生しない。"""
    # 非機能要件：区間分割数に依存せず付与量が一定になる。
    # Given
    parts = tuple(
        VoiceSegment(START + timedelta(microseconds=i), START + timedelta(microseconds=i + chunk_us), 1, 50)
        for i in range(0, 60_000_000, chunk_us)
    )
    # When
    step = take_voice_unit(parts, parts[-1].end)
    assert step.unit is not None
    award = calculate_voice_award(step.unit, 11, VoiceLimits(), ALL_PERIODS)
    # Then
    assert award.shard == ShardAward(3, 1)
    assert award.power == 3


@pytest.mark.parametrize("raw,expected", [(20, 2), (1, 0)])
def test_boundary_floor(raw: int, expected: int):
    """20秒境界は比例精算し、0量になっても時間端数を消費する。"""
    # 機能要件：切り捨てられた小数を翌期間に持ち越さない。
    # Given
    boundary = datetime(2027, 2, 1, tzinfo=JST)
    part = VoiceSegment(boundary - timedelta(seconds=20), boundary, 1)
    # When
    step = take_voice_unit([part], boundary)
    assert step.unit is not None
    award = calculate_voice_award(step.unit, raw, VoiceLimits(), ALL_PERIODS)
    # Then
    assert award.shard.total == award.power == expected
    assert step.remaining == ()


@pytest.mark.parametrize(
    "power,weights,expected",
    [
        (3, {2: 30, 1: 30}, {1: 2, 2: 1}),
        (7, {3: 1, 2: 2, 1: 3}, {1: 4, 2: 2, 3: 1}),
        (1, {3: 1, 2: 1, 1: 1}, {1: 1, 2: 0, 3: 0}),
        (0, {}, {}),
        (2, {1: 0, 2: 1}, {1: 0, 2: 2}),
    ],
)
def test_largest_remainder(power: int, weights: dict[int, int], expected: dict[int, int]):
    """チャンネルの入力順に依存せず最大剰余・ID昇順で合計を保存する。"""
    # 機能要件：VC間配分合計は実パワーに一致する。
    # Given / When
    result = allocate_power(power, weights)
    # Then
    assert result == expected
    assert sum(result.values()) == power
    assert allocate_power(power, dict(reversed(list(weights.items())))) == expected


@pytest.mark.parametrize(
    "shard,power,expected",
    [
        (300, 0, (0, 6)),
        (0, 300, (9, 0)),
        (300, 300, (0, 0)),
        (299, 299, (1, 1)),
        (400, 0, (0, 6)),
        (0, 400, (9, 0)),
        (295, 298, (5, 2)),
    ],
)
def test_independent_caps(shard: int, power: int, expected: tuple[int, int]):
    """シャード・パワーは独立して上限制御し、既存の上限超過残高を削らない。"""
    # 機能要件：残り枠は基本シャード優先で埋め、満杯側だけ停止する。
    # Given
    limits = VoiceLimits(shard, power)
    # When
    result = cap_voice_award(ShardAward(6, 3), 6, limits, ALL_PERIODS)
    # Then
    assert (result.shard.total, result.power) == expected
    assert result.shard.base == min(6, expected[0])
    assert result.next_limits.pending_shard == shard + expected[0]
    assert result.next_limits.pending_power == power + expected[1]


@pytest.mark.parametrize("accepted", [frozenset(), frozenset({PeriodKind.WEEK}), ALL_PERIODS])
def test_finalized_periods(accepted: frozenset[PeriodKind]):
    """全期間確定でも恒常シャードを保持し、不受理パワーは枠を消費しない。"""
    # 機能要件：DR06に従い期間受理と恒常成長を分離する。
    # Given
    unit = VoiceUnit((VoiceSegment(START, START + timedelta(seconds=60), 1),), START + timedelta(seconds=60))
    # When
    award = calculate_voice_award(unit, 20, VoiceLimits(), accepted)
    # Then
    assert award.shard.total == 6
    assert award.next_limits.pending_power == (6 if accepted else 0)
    assert dict(award.period_power) == {kind: 6 if kind in accepted else 0 for kind in PeriodKind}
    assert sum(dict(award.channel_power).values()) == award.power


def test_eligibility_and_clipped_distribution():
    """片側停止秒数を除外して計算し、上限適用後の整数を有効チャンネルへ配分する。"""
    # 機能要件：停止側の過去時間を枠解放後に付与しない。
    # Given
    unit = VoiceUnit(
        (
            VoiceSegment(START, START + timedelta(seconds=30), 1, shard_eligible=False),
            VoiceSegment(START + timedelta(seconds=30), START + timedelta(seconds=60), 2, power_eligible=False),
        ),
        START + timedelta(seconds=60),
    )
    # When
    award = calculate_voice_award(unit, 20, VoiceLimits(pending_power=298), ALL_PERIODS)
    # Then
    assert award.shard == ShardAward(3, 0)
    assert award.power == 2
    assert dict(award.channel_power) == {1: 2}


def test_fraction_precision():
    """重複ブーストをマイクロ秒単位で積分し、Decimal精度を下げても同じ値を返す。"""
    # 非機能要件：微小時間と巨大率の中間値を丸めない。
    # Given
    end = START + timedelta(seconds=60)
    boosts = [Boost(1, 1, 100, START, end), Boost(2, 1, 200, START + timedelta(microseconds=1), end)]
    unit = VoiceUnit(boosted_segments(START, end, 1, boosts, {1}), end)
    # When / Then
    with localcontext() as context:
        context.prec = 2
        result = calculate_voice_award(unit, 20, VoiceLimits(), ALL_PERIODS)
    assert result.shard == ShardAward(6, 17)
    assert result.power == 6
    with pytest.raises(ValueError):
        calculate_voice_award(unit, MAX_AMOUNT, VoiceLimits(), ALL_PERIODS, adjustment=Decimal(100))


@pytest.mark.parametrize("weights", [{1: -1}, {0: 1}, {1: 0}, {}])
def test_invalid_allocation(weights: dict[int, int]):
    """負の時間・不正ID・正の重みなしのパワー配分を拒否する。"""
    # 非機能要件：分配先のない数量を黙って失わない。
    # Given / When / Then
    with pytest.raises(ValueError):
        allocate_power(1, weights)

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.database.leveling_state import MAX_POWER, MAX_TOTAL_SHARD, PowerState, ShardState
from app.database.models.leveling_hotness import LevelingHotnessEventModel
from app.database.models.monthly_action_powers import MonthlyActionPowerModel
from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.models.star_grades import StarGradeModel
from tests.support.sqlite_database import SQLiteDatabase


@pytest.fixture
def db():
    database = SQLiteDatabase()
    yield database
    database.engine.dispose()


@pytest.mark.asyncio
async def test_sets_shards(db):
    """シャードを絶対値で設定し、増減・0リセットでグレードとプレステージも更新する。"""
    # 機能要件：復元値から進行度を再計算し、同じ値を再実行しても加算しない。
    # Given
    state = ShardState(268375, 100, 0)
    # When
    await db.leveling_state.set_shards(1, state)
    data = await db.leveling_state.set_shards(1, state)
    # Then
    assert (data.prestige, data.grade, data.shard) == (1, 1, 0)
    assert (data.text_shard, data.voice_shard, data.bonus_shard) == (268375, 100, 0)
    reset = await db.leveling_state.set_shards(1, ShardState())
    assert (reset.prestige, reset.grade, reset.shard) == (0, 0, 0)


@pytest.mark.asyncio
async def test_sets_powers_without_hotness(db):
    """パワー3種類を絶対値で復元し、活動量ランキングには新規活動として加算しない。"""
    # 機能要件：増加・減少・0を含むパワー値を保存する。
    # 非機能要件：復元では hotness を増やさない。
    # Given / When
    await db.leveling_state.set_powers(1, PowerState(100, 200, 300))
    await db.leveling_state.set_powers(1, PowerState(0, 2, MAX_POWER))
    # Then
    with Session(db.engine) as session:
        row = session.get(MonthlyPowerModel, 1)
        action = session.get(MonthlyActionPowerModel, 1)
        assert row is not None and action is not None
        assert (row.text_power, row.voice_power, action.action_power) == (0, 2, MAX_POWER)
        assert session.query(LevelingHotnessEventModel).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [ShardState(-1, 0, 0), ShardState(MAX_TOTAL_SHARD, 1, 0)])
async def test_rejects_invalid_shards(db, values):
    """負数と保存上限を超える合計は DB 更新前に拒否する。"""
    # 非機能要件：不正な復元値では行を新規作成しない。
    # Given / When
    with pytest.raises(ValueError):
        await db.leveling_state.set_shards(1, values)
    # Then
    with Session(db.engine) as session:
        assert session.get(StarGradeModel, 1) is None


def test_shard_upper_boundary():
    """保存可能なシャード合計の最大値を受け付ける。"""
    # 機能要件：上限ちょうどではプレステージ255に収まる。
    # Given / When / Then
    assert ShardState(MAX_TOTAL_SHARD).progression()[0] == 255

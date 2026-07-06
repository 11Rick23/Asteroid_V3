from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest

from app.database.models.monthly_action_powers import MonthlyActionPowerModel
from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.repositories.monthly_action_powers import MonthlyActionPowerData, MonthlyActionPowers
from app.database.repositories.monthly_powers import MonthlyPowerData, MonthlyPowers


class FakeSession:
    def __init__(self, model: object | None) -> None:
        self.model = model
        self.flush_count = 0
        self.refreshed: list[object] = []

    async def get(self, model_class: type[object], user_id: int) -> object | None:
        return self.model

    async def flush(self) -> None:
        self.flush_count += 1

    async def refresh(self, model: object) -> None:
        self.refreshed.append(model)
        now = datetime(2026, 6, 26, 1, 0)
        if isinstance(model, MonthlyPowerModel | MonthlyActionPowerModel):
            model.created_at = now
            model.updated_at = now


@pytest.mark.asyncio
async def test_remove_text_power_uses_current_model_amount() -> None:
    """text power 減算は古い DTO ではなく DB model の現在値を下限に丸める。"""
    # 機能要件：text power を指定量だけ減算し、更新後 DTO を返す。
    # 非機能要件：古い DTO を受け取っても DB model の現在値を負数にしない。
    # Given
    now = datetime(2026, 6, 26, 0, 0)
    model = MonthlyPowerModel(user_id=123, text_power=3, voice_power=10)
    model.created_at = now
    model.updated_at = now
    stale_data = MonthlyPowerData(123, 10, 10, 0, now, now)
    session = FakeSession(model)

    # When
    result = await MonthlyPowers(object()).remove_text_power_in_session(cast(Any, session), stale_data, 8)

    # Then
    assert result.text_power == 0
    assert model.text_power == 0
    assert session.flush_count == 1
    assert session.refreshed == [model]


@pytest.mark.asyncio
async def test_remove_voice_power_uses_current_model_amount() -> None:
    """voice power 減算は古い DTO ではなく DB model の現在値を下限に丸める。"""
    # 機能要件：voice power を指定量だけ減算し、更新後 DTO を返す。
    # 非機能要件：古い DTO を受け取っても DB model の現在値を負数にしない。
    # Given
    now = datetime(2026, 6, 26, 0, 0)
    model = MonthlyPowerModel(user_id=123, text_power=10, voice_power=3)
    model.created_at = now
    model.updated_at = now
    stale_data = MonthlyPowerData(123, 10, 10, 0, now, now)
    session = FakeSession(model)

    # When
    result = await MonthlyPowers(object()).remove_voice_power_in_session(cast(Any, session), stale_data, 8)

    # Then
    assert result.voice_power == 0
    assert model.voice_power == 0
    assert session.flush_count == 1
    assert session.refreshed == [model]


@pytest.mark.asyncio
async def test_remove_action_power_uses_current_model_amount() -> None:
    """action power 減算は古い DTO ではなく DB model の現在値を下限に丸める。"""
    # 機能要件：action power を指定量だけ減算し、更新後 DTO を返す。
    # 非機能要件：古い DTO を受け取っても DB model の現在値を負数にしない。
    # Given
    now = datetime(2026, 6, 26, 0, 0)
    model = MonthlyActionPowerModel(user_id=123, action_power=3)
    model.created_at = now
    model.updated_at = now
    stale_data = MonthlyActionPowerData(123, 10, now, now)
    session = FakeSession(model)

    # When
    result = await MonthlyActionPowers(object()).remove_action_power_in_session(cast(Any, session), stale_data, 8)

    # Then
    assert result.action_power == 0
    assert model.action_power == 0
    assert session.flush_count == 1
    assert session.refreshed == [model]

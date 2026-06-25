from __future__ import annotations

from datetime import datetime
from types import TracebackType

import pytest

from app.database.repositories.leveling import LevelingTransactions
from app.database.repositories.monthly_action_powers import MonthlyActionPowerData
from app.database.repositories.monthly_powers import MonthlyPowerData
from app.database.repositories.star_grades import StarGradeData
from app.database.repositories.voice_xp_limits import VoiceXPLimitData


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class FakeMonthlyActionPowers:
    def __init__(self, data: MonthlyActionPowerData) -> None:
        self.data = data

    async def get_monthly_action_power_in_session(
        self,
        session: FakeSession,
        user_id: int,
    ) -> MonthlyActionPowerData:
        return self.data

    async def add_action_power_in_session(
        self,
        session: FakeSession,
        data: MonthlyActionPowerData,
        amount: int,
    ) -> MonthlyActionPowerData:
        return MonthlyActionPowerData(
            user_id=data.user_id,
            action_power=data.action_power + amount,
            created_at=data.created_at,
            updated_at=datetime.now(),
        )


class FakeVoiceXPLimits:
    def __init__(self, data: VoiceXPLimitData) -> None:
        self.data = data
        self.deleted_user_id: int | None = None

    async def get_voice_xp_limit_in_session(self, session: FakeSession, user_id: int) -> VoiceXPLimitData:
        return self.data

    async def delete_voice_xp_limit_in_session(self, session: FakeSession, user_id: int) -> None:
        self.deleted_user_id = user_id


class FakeMonthlyPowers:
    def __init__(self) -> None:
        now = datetime.now()
        self.data = MonthlyPowerData(123, 10, 20, 0, now, now)

    async def get_monthly_power_in_session(self, session: FakeSession, user_id: int) -> MonthlyPowerData:
        return self.data

    async def add_text_power_in_session(
        self,
        session: FakeSession,
        data: MonthlyPowerData,
        amount: int,
    ) -> MonthlyPowerData:
        return MonthlyPowerData(
            data.user_id,
            data.text_power + amount,
            data.voice_power,
            data.action_power,
            data.created_at,
            datetime.now(),
        )

    async def add_voice_power_in_session(
        self,
        session: FakeSession,
        data: MonthlyPowerData,
        amount: int,
    ) -> MonthlyPowerData:
        return MonthlyPowerData(
            data.user_id,
            data.text_power,
            data.voice_power + amount,
            data.action_power,
            data.created_at,
            datetime.now(),
        )


class FakeStarGrades:
    def __init__(self, data: StarGradeData) -> None:
        self.data = data

    async def get_star_grade_in_session(self, session: FakeSession, user_id: int) -> StarGradeData:
        return self.data

    async def add_voice_shard_in_session(
        self,
        session: FakeSession,
        data: StarGradeData,
        amount: int,
    ) -> tuple[StarGradeData, int, int]:
        return data, 1, 0

    async def add_text_shard_in_session(
        self,
        session: FakeSession,
        data: StarGradeData,
        amount: int,
    ) -> tuple[StarGradeData, int, int]:
        return data, 0, 0

    async def add_bonus_shard_in_session(
        self,
        session: FakeSession,
        data: StarGradeData,
        amount: int,
    ) -> tuple[StarGradeData, int, int]:
        return data, 0, 1


class FakeLevelingHotness:
    def __init__(self) -> None:
        self.recorded: list[tuple[FakeSession, int, int]] = []

    async def record_gain_in_session(
        self,
        session: FakeSession,
        user_id: int,
        amount: int,
    ) -> None:
        self.recorded.append((session, user_id, amount))


class FakeDatabase:
    def __init__(
        self,
        *,
        session: FakeSession,
        monthly_action_powers: object | None = None,
        monthly_powers: object | None = None,
        star_grades: object | None = None,
        voice_xp_limits: object | None = None,
        leveling_hotness: object | None = None,
    ) -> None:
        self._session = session
        self.monthly_action_powers = monthly_action_powers
        self.monthly_powers = monthly_powers
        self.star_grades = star_grades
        self.voice_xp_limits = voice_xp_limits
        self.leveling_hotness = leveling_hotness

    def session(self) -> FakeSessionContext:
        return FakeSessionContext(self._session)


@pytest.mark.asyncio
async def test_add_action_power_commits() -> None:
    """action power 加算は hotness 記録と同一 session commit まで repository 内で完了する。"""
    # 機能要件：action power を加算し、更新後の DTO を返す。
    # 非機能要件：hotness 記録と action power 更新を同じ session で commit する。
    # Given
    now = datetime.now()
    session = FakeSession()
    hotness = FakeLevelingHotness()
    db = FakeDatabase(
        session=session,
        monthly_action_powers=FakeMonthlyActionPowers(MonthlyActionPowerData(123, 10, now, now)),
        leveling_hotness=hotness,
    )

    # When
    result = await LevelingTransactions(db).add_action_power(123, 5)

    # Then
    assert result.action_power == 15
    assert hotness.recorded == [(session, 123, 5)]
    assert session.committed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_text_power", "expected_voice_power"),
    [
        ("add_text_power", 15, 20),
        ("add_voice_power", 10, 25),
    ],
)
async def test_admin_power_additions_record_hotness(
    method_name: str,
    expected_text_power: int,
    expected_voice_power: int,
) -> None:
    """管理コマンド由来の text/voice power 加算は hotness にも同じ増分を記録する。"""
    # 機能要件：管理操作で monthly power を加算し、更新後の DTO を返す。
    # 非機能要件：ランキング用 hotness へ同じ session で増分を記録して commit する。
    # Given
    session = FakeSession()
    hotness = FakeLevelingHotness()
    db = FakeDatabase(session=session, monthly_powers=FakeMonthlyPowers(), leveling_hotness=hotness)

    # When
    result = await getattr(LevelingTransactions(db), method_name)(123, 5)

    # Then
    assert result.text_power == expected_text_power
    assert result.voice_power == expected_voice_power
    assert hotness.recorded == [(session, 123, 5)]
    assert session.committed is True


@pytest.mark.asyncio
async def test_message_reward_records_only_text_power() -> None:
    """メッセージ報酬は text power 分だけを hotness として記録する。"""
    # 機能要件：メッセージ報酬は text power と star grade を更新する。
    # 非機能要件：hotness には bonus shard 分ではなく text power 分だけを記録する。
    # Given
    now = datetime.now()
    session = FakeSession()
    hotness = FakeLevelingHotness()
    db = FakeDatabase(
        session=session,
        monthly_powers=FakeMonthlyPowers(),
        star_grades=FakeStarGrades(StarGradeData(123, 0, 0, 0, 0, 0, 0, now, now)),
        leveling_hotness=hotness,
    )

    # When
    await LevelingTransactions(db).apply_message_reward(123, 5, 10)

    # Then
    assert hotness.recorded == [(session, 123, 5)]
    assert session.committed is True


@pytest.mark.asyncio
async def test_claim_voice_xp_coordinates_repositories() -> None:
    """voice XP claim は関連 repository 更新、limit 削除、commit を 1 transaction で行う。"""
    # 機能要件：蓄積 voice XP を monthly power と star grade へ反映し、結果 DTO を返す。
    # 非機能要件：voice XP limit 削除と hotness 記録を同じ session で commit する。
    # Given
    now = datetime.now()
    session = FakeSession()
    voice_xp_limits = FakeVoiceXPLimits(VoiceXPLimitData(123, 10, 5, 20, False, False, now, now))
    hotness = FakeLevelingHotness()
    db = FakeDatabase(
        session=session,
        voice_xp_limits=voice_xp_limits,
        monthly_powers=FakeMonthlyPowers(),
        star_grades=FakeStarGrades(StarGradeData(123, 0, 0, 0, 0, 0, 0, now, now)),
        leveling_hotness=hotness,
    )

    # When
    result = await LevelingTransactions(db).claim_voice_xp(123)

    # Then
    assert result is not None
    assert result.grade_up_amount == 1
    assert result.prestige_amount == 1
    assert voice_xp_limits.deleted_user_id == 123
    assert hotness.recorded == [(session, 123, 20)]
    assert session.committed is True

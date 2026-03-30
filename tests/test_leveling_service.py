from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.database.repositories.star_grades import StarGradeData
from app.database.repositories.voice_xp_limits import VoiceXPLimitData
from app.features.leveling.service import VoiceXPClaimResult, build_voice_xp_claim_message, claim_voice_xp_rewards


class FakeUser:
    mention = "<@123>"


def test_build_voice_xp_claim_message_formats_claim_summary() -> None:
    now = datetime.now()
    claim_result = VoiceXPClaimResult(
        voice_xp_limit=VoiceXPLimitData(123, 1200, 30, 45, False, False, now, now),
        star_grade=StarGradeData(123, 2, 10, 0, 0, 0, 0, now, now),
        grade_up_amount=1,
        prestige_amount=0,
    )

    message = build_voice_xp_claim_message(FakeUser(), claim_result)

    assert message == (
        "<@123> ボイスシャードを`1.2K`獲得しました\n"
        "ボイスパワーを`45`獲得しました\n"
        "ボイスボーナスシャードを`30`獲得しました"
    )


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

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeVoiceXPLimits:
    def __init__(self, data: VoiceXPLimitData) -> None:
        self.data = data
        self.deleted_user_id: int | None = None

    async def get_voice_xp_limit_lock(self, session: FakeSession, user_id: int) -> VoiceXPLimitData | None:
        return self.data

    async def delete_voice_xp_limit_lock(self, session: FakeSession, user_id: int) -> None:
        self.deleted_user_id = user_id


class FakeMonthlyPowers:
    async def get_monthly_power_lock(self, session: FakeSession, user_id: int) -> None:
        return None

    async def create_monthly_power_lock(self, session: FakeSession, user_id: int) -> SimpleNamespace:
        return SimpleNamespace(user_id=user_id)

    async def add_voice_power_lock(self, session: FakeSession, monthly_power: SimpleNamespace, value: int) -> None:
        return None


class FakeStarGrades:
    def __init__(self, star_grade: StarGradeData) -> None:
        self.star_grade = star_grade

    async def get_star_grade_lock(self, session: FakeSession, user_id: int) -> StarGradeData:
        return self.star_grade

    async def add_voice_shard_lock(
        self, session: FakeSession, star_grade: StarGradeData, value: int
    ) -> tuple[StarGradeData, int, int]:
        return self.star_grade, 1, 0

    async def add_bonus_shard_lock(
        self, session: FakeSession, star_grade: StarGradeData, value: int
    ) -> tuple[StarGradeData, int, int]:
        return self.star_grade, 0, 0


@pytest.mark.asyncio
async def test_claim_voice_xp_rewards_logs_success(caplog) -> None:
    now = datetime.now()
    session = FakeSession()
    bot = SimpleNamespace()
    bot.db = SimpleNamespace(
        session=lambda: FakeSessionContext(session),
        voice_xp_limits=FakeVoiceXPLimits(VoiceXPLimitData(123, 120, 30, 45, False, False, now, now)),
        monthly_powers=FakeMonthlyPowers(),
        star_grades=FakeStarGrades(StarGradeData(123, 1, 5, 0, 0, 0, 0, now, now)),
    )

    with caplog.at_level(logging.INFO, logger="app.features.leveling.service"):
        result = await claim_voice_xp_rewards(bot, 123)

    assert result is not None
    assert "VC経験値を受け取りました: user_id=123" in caplog.text
    assert session.committed is True

from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.database.repositories.leveling import VoiceXPClaimData
from app.database.repositories.star_grades import StarGradeData
from app.database.repositories.voice_xp_limits import VoiceXPLimitData
from app.features.leveling.service import build_voice_xp_claim_message, claim_voice_xp_rewards


class FakeUser:
    mention = "<@123>"


def test_build_voice_xp_claim_message_formats_claim_summary() -> None:
    now = datetime.now()
    claim_result = VoiceXPClaimData(
        voice_xp_limit=VoiceXPLimitData(123, 1200, 30, 45, False, False, now, now),
        star_grade=StarGradeData(123, 2, 10, 0, 0, 0, 0, now, now),
        grade_up_amount=1,
        prestige_amount=0,
    )

    message = build_voice_xp_claim_message(cast(discord.User, FakeUser()), claim_result)

    assert message == (
        "<@123> ボイスシャードを`1.2K`獲得しました\n"
        "ボイスパワーを`45`獲得しました\n"
        "ボイスボーナスシャードを`30`獲得しました"
    )


class FakeLevelingTransactions:
    def __init__(self, claim_result: VoiceXPClaimData) -> None:
        self.claim_result = claim_result

    async def claim_voice_xp(self, user_id: int) -> VoiceXPClaimData:
        return self.claim_result


@pytest.mark.asyncio
async def test_claim_voice_xp_rewards_logs_success(caplog) -> None:
    now = datetime.now()
    bot = SimpleNamespace()
    claim_result = VoiceXPClaimData(
        voice_xp_limit=VoiceXPLimitData(123, 120, 30, 45, False, False, now, now),
        star_grade=StarGradeData(123, 1, 5, 0, 0, 0, 0, now, now),
        grade_up_amount=1,
        prestige_amount=0,
    )
    bot.db = SimpleNamespace(
        leveling=FakeLevelingTransactions(claim_result),
    )

    with caplog.at_level(logging.DEBUG, logger="app.features.leveling.service"):
        result = await claim_voice_xp_rewards(cast(AsteroidBot, bot), 123)

    assert result is not None
    assert "VC経験値を受け取りました: user_id=123" in caplog.text

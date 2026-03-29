from __future__ import annotations

from datetime import datetime

from app.database.repositories.star_grades import StarGradeData
from app.database.repositories.voice_xp_limits import VoiceXPLimitData
from app.features.leveling.service import VoiceXPClaimResult, build_voice_xp_claim_message


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

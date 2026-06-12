from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import send_grade_up_message
from app.features.leveling.views import ClaimVoiceXP


class FakeChannel:
    def __init__(self) -> None:
        self.send_calls: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> None:
        self.send_calls.append(kwargs)


def text_contents(view: discord.ui.LayoutView) -> str:
    return "\n".join(
        child.content for child in view.walk_children() if isinstance(child, discord.ui.TextDisplay)
    )


def test_claim_voice_xp_uses_container_and_persistent_button() -> None:
    view = ClaimVoiceXP(cast(AsteroidBot, SimpleNamespace()))

    assert view.timeout is None
    assert view.has_components_v2()
    assert "# VC経験値獲得はこちら" in text_contents(view)
    button = next(child for child in view.walk_children() if isinstance(child, discord.ui.Button))
    assert button.label == "VC経験値を獲得する"
    assert button.custom_id == "claim_voice_xp"


@pytest.mark.asyncio
async def test_grade_up_notification_sends_components_v2_view() -> None:
    channel = FakeChannel()
    author = cast(discord.User, SimpleNamespace(mention="<@100>"))

    await send_grade_up_message(cast(discord.abc.Messageable, channel), author, 5, 2)

    assert len(channel.send_calls) == 1
    assert set(channel.send_calls[0]) == {"view"}
    view = channel.send_calls[0]["view"]
    assert isinstance(view, discord.ui.LayoutView)
    assert "# レベルアップ！" in text_contents(view)
    assert "Grade. 3からGrade. 5" in text_contents(view)

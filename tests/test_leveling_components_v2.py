from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    send_grade_up_message,
    send_prestige_announce,
    send_prestige_up_message,
)
from app.features.leveling.views import ClaimVoiceXP


class FakeChannel:
    def __init__(self) -> None:
        self.send_calls: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> discord.Message:
        self.send_calls.append(kwargs)
        return cast(discord.Message, SimpleNamespace())


class FakeGuild:
    def get_role(self, role_id: int) -> Any:
        return SimpleNamespace(mention=f"<@&{role_id}>")


def text_contents(view: discord.ui.LayoutView) -> str:
    return "\n".join(child.content for child in view.walk_children() if isinstance(child, discord.ui.TextDisplay))


def test_claim_voice_xp_uses_container_and_persistent_button() -> None:
    view = ClaimVoiceXP(cast(AsteroidBot, SimpleNamespace()))

    assert view.timeout is None
    assert view.has_components_v2()
    assert "# VC経験値獲得はこちら" in text_contents(view)
    button = next(child for child in view.walk_children() if isinstance(child, discord.ui.Button))
    assert button.label == "VC経験値を獲得する"
    assert button.custom_id == "claim_voice_xp"


@pytest.mark.asyncio
async def test_grade_up_notification_sends_embed() -> None:
    channel = FakeChannel()
    author = cast(discord.User, SimpleNamespace(mention="<@100>"))

    await send_grade_up_message(cast(discord.abc.Messageable, channel), author, 5, 2)

    assert len(channel.send_calls) == 1
    assert set(channel.send_calls[0]) == {"embed"}
    embed = channel.send_calls[0]["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.title == "レベルアップ！"
    assert embed.description == "<@100>さんがGrade. 3からGrade. 5へグレードアップ！"


@pytest.mark.asyncio
async def test_prestige_up_notification_sends_embed() -> None:
    channel = FakeChannel()
    author = cast(discord.User, SimpleNamespace(mention="<@100>"))

    await send_prestige_up_message(cast(discord.abc.Messageable, channel), author, 3, 1)

    assert len(channel.send_calls) == 1
    assert set(channel.send_calls[0]) == {"embed"}
    embed = channel.send_calls[0]["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.title == "プレステージ！"
    assert embed.description == "<@100>さんがPrestige. 2からPrestige. 3へプレステージ！"


@pytest.mark.asyncio
async def test_prestige_announce_sends_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = FakeChannel()
    monkeypatch.setattr("app.features.leveling.build_send_message.as_messageable", lambda target: target)
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            config=SimpleNamespace(
                leveling=SimpleNamespace(
                    prestige_roles_id_list=[SimpleNamespace(prestige=2, role_id=200)],
                    prestige_announce_channel_id=300,
                )
            ),
            get_channel=lambda channel_id: channel,
            is_operating_channel=lambda target: target is channel,
        ),
    )
    member = cast(discord.Member, SimpleNamespace(mention="<@100>", guild=FakeGuild()))

    await send_prestige_announce(bot, member, 3)

    assert len(channel.send_calls) == 1
    assert set(channel.send_calls[0]) == {"embed"}
    embed = channel.send_calls[0]["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.title == "プレステージ達成！"
    assert embed.description == "<@100>さんが<@&200>を達成しました！\nおめでとうございます！"
    assert embed.color is not None
    assert embed.color.value == AsteroidColor.SUCCESS

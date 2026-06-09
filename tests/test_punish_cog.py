from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.punish import cog
from app.features.punish.cog import PermRoleSelect, punish_group


def test_all_punish_commands_are_guild_only() -> None:
    commands = list(punish_group.walk_commands())

    assert commands
    assert all(command.guild_only is True for command in commands)


class DummyResponse:
    def __init__(self) -> None:
        self.send_message_calls: list[tuple[str, bool]] = []
        self.edit_message_calls: list[tuple[str, object | None]] = []

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.send_message_calls.append((content, ephemeral))

    async def edit_message(self, *, content: str, view: object | None = None) -> None:
        self.edit_message_calls.append((content, view))


class DummyInteraction:
    def __init__(self) -> None:
        self.guild = None
        self.user = SimpleNamespace(id=1)
        self.response = DummyResponse()


@pytest.mark.asyncio
async def test_perm_role_select_callback_rejects_dm_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def fake_give_crime_record_role(*args: object, **kwargs: object) -> bool:
        nonlocal called
        called = True
        return False

    monkeypatch.setattr(cog, "give_crime_record_role", fake_give_crime_record_role)

    select = PermRoleSelect(
        bot=cast(AsteroidBot, object()),
        target=cast(discord.Member, object()),
        select_options=[discord.SelectOption(label="role", value="1")],
        reason="reason",
        probation=None,
    )
    interaction = DummyInteraction()

    await select.callback(cast(discord.Interaction, interaction))

    assert called is False
    assert interaction.response.send_message_calls == [("サーバー内でのみ使用できます。", True)]


class DummyPunishBoard:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        self.messages.append(message)


class DummyTargetUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.name = "target"

    async def send(self, message: str) -> None:
        return None


class DummyGuild:
    def __init__(self, board: DummyPunishBoard) -> None:
        self.id = 100
        self._board = board

    def get_member(self, user_id: int) -> None:
        return None

    def get_channel(self, channel_id: int) -> DummyPunishBoard:
        return self._board

    def get_role(self, role_id: int) -> None:
        return None


class DummyMuteInteraction:
    def __init__(self, guild: DummyGuild) -> None:
        self.guild = guild
        self.user = SimpleNamespace(id=55, name="moderator")
        self.response = DummyResponse()


@pytest.mark.asyncio
async def test_mute_logs_when_target_member_is_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    board = DummyPunishBoard()
    interaction = DummyMuteInteraction(DummyGuild(board))
    bot = SimpleNamespace(
        config=SimpleNamespace(
            punish=SimpleNamespace(
                punishment_board_channel_id=999,
                mute_role_id=123,
                crime_record_role_id_list=[],
            )
        )
    )
    monkeypatch.setattr(cog, "get_bot", lambda _: bot)

    async def fake_require_punishment_context(*args: object, **kwargs: object):
        return interaction.guild, interaction.user, board

    monkeypatch.setattr(cog, "require_punishment_context", fake_require_punishment_context)

    with caplog.at_level(logging.INFO, logger="app.features.punish.cog"):
        await cast(Any, cog.mute.callback)(interaction, DummyTargetUser(77), "reason", None)

    assert "処罰を実行します: action=MUTE" in caplog.text
    assert "前科ロールの付与対象メンバーが見つかりませんでした: guild_id=100 target_id=77" in caplog.text
    assert interaction.response.send_message_calls

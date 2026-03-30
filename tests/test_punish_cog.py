from __future__ import annotations

import discord
import pytest

from app.features.punish import cog
from app.features.punish.cog import PermRoleSelect, punish_group


def test_all_punish_commands_are_guild_only() -> None:
    commands = list(punish_group.walk_commands())

    assert commands
    assert all(command.guild_only is True for command in commands)


class DummyResponse:
    def __init__(self) -> None:
        self.send_message_calls: list[tuple[str, bool]] = []

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.send_message_calls.append((content, ephemeral))


class DummyInteraction:
    def __init__(self) -> None:
        self.guild = None
        self.user = object()
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
        bot=object(),
        target=object(),
        select_options=[discord.SelectOption(label="role", value="1")],
        reason="reason",
        probation=None,
    )
    interaction = DummyInteraction()

    await select.callback(interaction)

    assert called is False
    assert interaction.response.send_message_calls == [("サーバー内でのみ使用できます。", True)]

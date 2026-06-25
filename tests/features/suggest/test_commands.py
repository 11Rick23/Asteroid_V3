from __future__ import annotations

from typing import Any, cast

import pytest
from discord import app_commands

from app.features.suggest import cog
from app.features.suggest.cog import suggest_group
from tests.support.discord_fakes import FakeUser


class _SuggestConfig:
    suggestion_forum_channel_id = 10


class _Config:
    suggest = _SuggestConfig()


class _Bot:
    config = _Config()


class _Response:
    def __init__(self) -> None:
        self.deferred = False

    async def defer(self) -> None:
        self.deferred = True


class _Followup:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send(self, **kwargs: object) -> None:
        self.sent_messages.append(kwargs)


class _ForumChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id


class _Thread:
    id = 20

    def __init__(self, parent: object) -> None:
        self.parent = parent
        self.archived_values: list[bool] = []

    async def edit(self, *, archived: bool) -> None:
        self.archived_values.append(archived)


class _Avatar:
    url = "https://example.invalid/avatar.png"


class _Actor(FakeUser):
    display_name = "moderator"
    display_avatar = _Avatar()


class _Interaction:
    def __init__(self, channel: object) -> None:
        self.channel = channel
        self.channel_id = getattr(channel, "id", None)
        self.guild_id = 123
        self.user = _Actor(100)
        self.response = _Response()
        self.followup = _Followup()


def test_group_is_admin_only():
    """suggestion group は guild 限定で管理者権限をデフォルト権限にする。"""
    # 機能要件：suggestion group は要望管理 command group として登録される。
    # 非機能要件：suggestion group は guild 限定かつ管理者向け権限で公開される。
    # Given / When / Then
    assert suggest_group.name == "suggestion"
    assert suggest_group.guild_only is True
    assert suggest_group.default_permissions is not None
    assert suggest_group.default_permissions.administrator is True


def test_reason_is_japanese():
    """approve / deny の公開引数名と説明は日本語で登録する。"""
    # 機能要件：approve / deny の理由引数は日本語名と説明で公開される。
    # Given
    approve = suggest_group.get_command("approve")
    deny = suggest_group.get_command("deny")

    # When / Then
    assert approve is not None
    assert deny is not None
    approve_command = cast(app_commands.Command, approve)
    deny_command = cast(app_commands.Command, deny)
    assert approve_command.parameters[0].display_name == "理由"
    assert approve_command.parameters[0].description == "要望を可決する理由"
    assert deny_command.parameters[0].display_name == "理由"
    assert deny_command.parameters[0].description == "要望を否決する理由"


@pytest.mark.asyncio
async def test_approves_forum_thread(monkeypatch):
    """要望フォーラム配下のスレッドでは判定結果を送信し、スレッドをアーカイブする。"""
    # 機能要件：要望フォーラム配下のスレッドでは判定結果を送信してスレッドをアーカイブする。
    # Given
    thread = _Thread(_ForumChannel(10))
    interaction = _Interaction(thread)
    monkeypatch.setattr(cog, "get_bot", lambda _interaction: _Bot())
    monkeypatch.setattr(cog.discord, "Thread", _Thread)
    monkeypatch.setattr(cog.discord, "ForumChannel", _ForumChannel)

    # When
    await cog.suggestion_handler(cast(Any, interaction), "可決", "よい提案です")

    # Then
    assert interaction.response.deferred is True
    assert thread.archived_values == [True]
    assert len(interaction.followup.sent_messages) == 1
    assert interaction.followup.sent_messages[0].get("ephemeral") is None


@pytest.mark.asyncio
async def test_rejects_non_suggestion_thread(monkeypatch):
    """要望フォーラム外のスレッドでは判定処理を行わず、本人向けに拒否通知する。"""
    # 非機能要件：要望フォーラム外のスレッドではスレッドをアーカイブしない。
    # Given
    thread = _Thread(_ForumChannel(999))
    interaction = _Interaction(thread)
    monkeypatch.setattr(cog, "get_bot", lambda _interaction: _Bot())
    monkeypatch.setattr(cog.discord, "Thread", _Thread)
    monkeypatch.setattr(cog.discord, "ForumChannel", _ForumChannel)

    # When
    await cog.suggestion_handler(cast(Any, interaction), "否決", "対象外です")

    # Then
    assert interaction.response.deferred is True
    assert thread.archived_values == []
    assert len(interaction.followup.sent_messages) == 1
    assert interaction.followup.sent_messages[0]["ephemeral"] is True

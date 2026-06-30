from __future__ import annotations

from typing import Any, cast

import pytest
from discord import app_commands

from app.features.birthday import cog
from app.features.birthday.cog import birthday_group
from tests.support.discord_fakes import FakeUser


class _Response:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send_message(self, **kwargs: object) -> None:
        self.sent_messages.append(kwargs)


class _Interaction:
    def __init__(self) -> None:
        self.user = FakeUser(100)
        self.guild_id = 123
        self.channel_id = 456
        self.response = _Response()


class _UserBirthdays:
    def __init__(self) -> None:
        self.upserts: list[tuple[int, object]] = []
        self.deleted_user_ids: list[int] = []

    async def upsert_data(self, user_id: int, birthday: object) -> None:
        self.upserts.append((user_id, birthday))

    async def delete_data(self, user_id: int) -> None:
        self.deleted_user_ids.append(user_id)


class _DB:
    def __init__(self) -> None:
        self.user_birthdays = _UserBirthdays()


class _Bot:
    def __init__(self) -> None:
        self.db = _DB()


def test_set_arguments_are_japanese():
    """誕生日設定 command の公開引数名は日本語で登録する。"""
    # 機能要件：誕生日設定 command は月と日を日本語引数として公開する。
    # Given
    command = birthday_group.get_command("set")

    # When / Then
    assert isinstance(command, app_commands.Command)
    assert [parameter.display_name for parameter in command.parameters] == ["月", "日"]


def test_set_others_is_admin_only():
    """他人の誕生日設定 command は管理者向け権限を持つ。"""
    # 非機能要件：他人の誕生日を変更する command は管理者向け権限で公開される。
    # Given
    command = birthday_group.get_command("set_others")

    # When / Then
    assert isinstance(command, app_commands.Command)
    assert command.default_permissions is not None
    assert command.default_permissions.administrator is True
    assert [parameter.display_name for parameter in command.parameters] == ["ユーザー", "月", "日"]


@pytest.mark.asyncio
async def test_rejects_invalid_set_date(monkeypatch):
    """存在しない日付の誕生日設定では DB に保存しない。"""
    # 非機能要件：存在しない日付の誕生日設定では DB 書き込みを行わない。
    # Given
    bot = _Bot()
    interaction = _Interaction()
    monkeypatch.setattr(cog, "get_bot", lambda _interaction: bot)

    # When
    await cast(Any, cog.birthday_set.callback)(interaction, 2, 30)

    # Then
    assert bot.db.user_birthdays.upserts == []
    assert len(interaction.response.sent_messages) == 1


@pytest.mark.asyncio
async def test_rejects_other_user_remove_without_admin(monkeypatch):
    """管理者ではないユーザーは他人の誕生日を削除できない。"""
    # 非機能要件：管理者以外が他人の誕生日削除を要求しても DB 削除を行わない。
    # Given
    bot = _Bot()
    interaction = _Interaction()
    target = FakeUser(200)
    monkeypatch.setattr(cog, "get_bot", lambda _interaction: bot)

    # When
    await cast(Any, cog.birthday_remove.callback)(interaction, target)

    # Then
    assert bot.db.user_birthdays.deleted_user_ids == []
    assert len(interaction.response.sent_messages) == 1

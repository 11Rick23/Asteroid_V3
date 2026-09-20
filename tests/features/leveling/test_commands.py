from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from app.features.leveling.commands import admin_command
from app.features.leveling.commands.admin_command import leveling_admin_group, xp_boost_add
from app.features.leveling.commands.command import transfer_mee6

boost_callback = cast(
    Callable[[discord.Interaction, discord.Role, str, int, str | None], Awaitable[None]], xp_boost_add.callback
)


def test_admin_group_is_admin_only():
    """管理者用レベリング group は guild 限定で管理者権限をデフォルト権限にする。"""
    # 非機能要件：レベリング管理 group は guild 限定かつ管理者向け権限で公開される。
    # Given / When / Then
    assert leveling_admin_group.name == "leveling"
    assert leveling_admin_group.guild_only is True
    assert leveling_admin_group.default_permissions is not None
    assert leveling_admin_group.default_permissions.administrator is True


def test_transfer_mee6_metadata():
    """MEE6 移行 setup command は guild 限定で日本語引数を公開する。"""
    # 機能要件：MEE6 移行 command はロール同期とプレステージ通知の指定を公開する。
    # 非機能要件：MEE6 移行 command は guild 限定かつ管理者向け command として登録する。
    # Given / When / Then
    assert transfer_mee6.guild_only is True
    assert transfer_mee6.default_permissions is not None
    assert transfer_mee6.default_permissions.administrator is True
    assert [parameter.display_name for parameter in transfer_mee6.parameters] == ["ロール同期", "プレステージ通知"]


def test_booster_options():
    """倍率の％表記と入力例を説明し、期間を任意引数として公開する。"""
    # 機能要件：2倍にする入力値と期間の入力形式、省略時の挙動をコマンドで確認できる。
    # Given / When
    parameters = {parameter.name: parameter for parameter in xp_boost_add.parameters}

    # Then
    assert [parameter.display_name for parameter in parameters.values()] == ["ロール", "名前", "倍率", "期間"]
    assert "％" in parameters["amount"].description
    assert "200で2倍" in parameters["amount"].description
    assert "1d12h" in parameters["duration"].description
    assert "無期限" in parameters["duration"].description
    assert parameters["duration"].required is False
    assert parameters["duration"].default is None


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", [None, "1s", "1d12h"])
async def test_booster_expiration(duration, monkeypatch, caplog):
    """期間に応じた UTC 終了日時を保存し、省略時は無期限にする。"""
    # 機能要件：期間指定で期限付きブースターを作成し、倍率は％の値のまま保存する。
    # 非機能要件：登録した期限を監査ログに残す。
    # Given
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return now

    monkeypatch.setattr(admin_command, "datetime", FixedDatetime)
    create = AsyncMock()
    send = AsyncMock()
    interaction = SimpleNamespace(
        client=SimpleNamespace(db=SimpleNamespace(xp_boosts=SimpleNamespace(create_xp_boost=create))),
        guild_id=1,
        channel_id=2,
        user=SimpleNamespace(id=3),
        response=SimpleNamespace(send_message=send),
    )
    delta = {None: None, "1s": timedelta(seconds=1), "1d12h": timedelta(days=1, hours=12)}[duration]
    expected = now.replace(tzinfo=None) + delta if delta is not None else None

    # When
    with caplog.at_level("INFO", logger=admin_command.__name__):
        await boost_callback(
            cast(discord.Interaction, interaction), cast(discord.Role, SimpleNamespace(id=4)), "週末", 200, duration
        )

    # Then
    create.assert_awaited_once_with(4, "週末", 200, expected)
    send.assert_awaited_once_with(admin_command.admin_messages.BOOSTER_ADDED)
    assert f"end_time={expected}" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", ["", "0s", "-1d", "1日", "1h typo", "999999999999999w", "999999999d"])
async def test_booster_invalid_duration(duration):
    """不正な形式、0 以下、日時の範囲を超える期間では保存せず非公開でエラーを返す。"""
    # 機能要件：無効な期間の入力には修正方法を示す。
    # 非機能要件：入力拒否時には DB を更新しない。
    # Given
    create = AsyncMock()
    send = AsyncMock()
    interaction = SimpleNamespace(
        client=SimpleNamespace(db=SimpleNamespace(xp_boosts=SimpleNamespace(create_xp_boost=create))),
        response=SimpleNamespace(send_message=send),
    )

    # When
    await boost_callback(
        cast(discord.Interaction, interaction), cast(discord.Role, SimpleNamespace(id=4)), "週末", 200, duration
    )

    # Then
    create.assert_not_awaited()
    send.assert_awaited_once_with(admin_command.admin_messages.BOOSTER_INVALID_DURATION, ephemeral=True)


@pytest.mark.parametrize("command", [admin_command.remove_shard, admin_command.remove_power])
def test_remove_amount_range(command):
    """減算コマンドの数量は1以上に制限する。"""
    # 機能要件：Discord の入力欄で負数と0を拒否する。
    # Given / When / Then
    parameter = next(parameter for parameter in command.parameters if parameter.name == "amount")
    assert parameter.min_value == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("command", [admin_command.remove_shard, admin_command.remove_power])
@pytest.mark.parametrize("amount", [-10, 0])
async def test_rejects_invalid_removal(command, amount):
    """負数や0を渡しても減算処理を実行せず、非公開で入力エラーを返す。"""
    # 非機能要件：不正な数量で DB 更新やロール同期を実行しない。
    # Given
    repository = SimpleNamespace(remove_shard=AsyncMock(), remove_power=AsyncMock())
    interaction = SimpleNamespace(
        client=SimpleNamespace(db=SimpleNamespace(leveling=repository)),
        response=SimpleNamespace(send_message=AsyncMock()),
    )

    # When
    await cast(Any, command.callback)(interaction, SimpleNamespace(id=4), SimpleNamespace(value="text"), amount)

    # Then
    repository.remove_shard.assert_not_awaited()
    repository.remove_power.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once_with(
        admin_command.admin_messages.POSITIVE_AMOUNT_REQUIRED, ephemeral=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["shard", "power"])
async def test_removes_one(kind, monkeypatch):
    """数量の下限である1は指定対象からの減算として受け付ける。"""
    # 機能要件：正の数量による既存の減算と応答を維持する。
    # Given
    result = SimpleNamespace(star_grade=SimpleNamespace(grade=0, prestige=0))
    remove = AsyncMock(return_value=result)
    repository = SimpleNamespace(**{f"remove_{kind}": remove})
    interaction = SimpleNamespace(
        client=SimpleNamespace(db=SimpleNamespace(leveling=repository)),
        guild_id=1,
        channel_id=2,
        user=SimpleNamespace(id=3),
        response=SimpleNamespace(send_message=AsyncMock()),
    )
    monkeypatch.setattr(admin_command, "build_star_grade_view", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin_command, "build_power_view", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin_command, "sync_grade_prestige_role", AsyncMock())
    command = admin_command.remove_shard if kind == "shard" else admin_command.remove_power
    target_type = "テキスト" if kind == "shard" else "text"

    # When
    await cast(Any, command.callback)(
        interaction, SimpleNamespace(id=4, mention="<@4>"), SimpleNamespace(value=target_type), 1
    )

    # Then
    remove.assert_awaited_once_with(4, target_type, 1)
    interaction.response.send_message.assert_awaited_once()

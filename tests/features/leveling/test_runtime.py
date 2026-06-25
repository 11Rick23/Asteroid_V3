from __future__ import annotations

from typing import Any, cast

import pytest

from app.features.leveling.message_handler import LevelingMessageHandler
from app.features.leveling.monthly import run_monthly_ranking


class _LevelingConfig:
    action_power_channel_id = 10
    message_cooldown = 15
    min_xp_per_message = 10
    max_xp_per_message = 25
    voice_xp_adjust = 0.3


class _Config:
    leveling = _LevelingConfig()


class _LevelingRepository:
    def __init__(self) -> None:
        self.added_action_powers: list[tuple[int, int]] = []

    async def add_action_power(self, user_id: int, value: int) -> None:
        self.added_action_powers.append((user_id, value))


class _XPBoostsRepository:
    async def get_xp_boosts(self) -> list[object]:
        return []


class _Database:
    def __init__(self) -> None:
        self.leveling = _LevelingRepository()
        self.xp_boosts = _XPBoostsRepository()


class _Bot:
    config = _Config()

    def __init__(self, *, operating: bool = True) -> None:
        self.operating = operating
        self.db = _Database()
        self.remembered_messages: list[object] = []

    def is_operating_guild(self, _guild: object) -> bool:
        return self.operating

    def remember_message(self, message: object) -> None:
        self.remembered_messages.append(message)


class _Author:
    id = 999
    bot = True


class _Channel:
    id = 10


class _Guild:
    id = 12345

    def get_member(self, user_id: int) -> object | None:
        return object() if user_id == 123 else None


class _Message:
    def __init__(self, *, guild: object | None = None, content: str = "AddActionPower 123 45 reason") -> None:
        self.guild = guild or _Guild()
        self.author = _Author()
        self.channel = _Channel()
        self.content = content
        self.reactions: list[str] = []

    async def add_reaction(self, emoji: str) -> None:
        self.reactions.append(emoji)


@pytest.mark.asyncio
async def test_skips_outside_guild():
    """対象外 guild の message ではキャッシュ更新や経験値処理を行わない。"""
    # 非機能要件：対象外 guild の message ではメッセージキャッシュや DB 更新を行わない。
    # Given
    bot = _Bot(operating=False)
    handler = LevelingMessageHandler(cast(Any, bot))
    message = _Message()

    # When
    await handler.handle(cast(Any, message))

    # Then
    assert bot.remembered_messages == []
    assert bot.db.leveling.added_action_powers == []


@pytest.mark.asyncio
async def test_handles_action_power_command():
    """action power チャンネルの有効な BOT コマンドは DB 加算してリアクションを付ける。"""
    # 機能要件：action power チャンネルの有効な BOT コマンドは対象ユーザーへ加算する。
    # 非機能要件：処理済み command には確認リアクションを付ける。
    # Given
    bot = _Bot()
    handler = LevelingMessageHandler(cast(Any, bot))
    message = _Message()

    # When
    handled = await handler._try_action_power_command(cast(Any, message))

    # Then
    assert handled is True
    assert bot.db.leveling.added_action_powers == [(123, 45)]
    assert message.reactions == ["✅"]


@pytest.mark.asyncio
async def test_ignores_missing_action_power_target():
    """存在しないユーザーへの action power コマンドは DB 加算しない。"""
    # 非機能要件：guild に存在しないユーザー ID への action power 加算は行わない。
    # Given
    bot = _Bot()
    handler = LevelingMessageHandler(cast(Any, bot))
    message = _Message(content="AddActionPower 999 45 reason")

    # When
    handled = await handler._try_action_power_command(cast(Any, message))

    # Then
    assert handled is False
    assert bot.db.leveling.added_action_powers == []
    assert message.reactions == []


class _MonthlyPowersRepository:
    async def get_monthly_power_ranking(self, limit: int) -> list[object]:
        return []


class _MonthlyActionPowersRepository:
    async def sum_action_power(self) -> int:
        return 0


class _MonthlyLevelingRepository:
    def __init__(self) -> None:
        self.reset_count = 0

    async def reset_monthly_power_state(self) -> None:
        self.reset_count += 1


class _MonthlyDatabase:
    def __init__(self) -> None:
        self.leveling = _MonthlyLevelingRepository()
        self.monthly_powers = _MonthlyPowersRepository()
        self.monthly_action_powers = _MonthlyActionPowersRepository()

    def is_initialized(self) -> bool:
        return True


class _MonthlyLevelingConfig:
    month_ranking_board_channel_id = 20
    action_power_channel_id = 21
    top1_role_id = 30
    top10_role_id = 31


class _MonthlyDiscordConfig:
    guild_id = 12345


class _MonthlyConfig:
    leveling = _MonthlyLevelingConfig()
    discord = _MonthlyDiscordConfig()


class _MonthlyGuild:
    id = 12345

    def get_role(self, role_id: int) -> None:
        return None


class _MonthlyBot:
    config = _MonthlyConfig()

    def __init__(self) -> None:
        self.db = _MonthlyDatabase()

    def get_guild(self, guild_id: int) -> _MonthlyGuild | None:
        return _MonthlyGuild() if guild_id == 12345 else None

    def get_channel(self, channel_id: int) -> None:
        return None

    def is_operating_channel(self, channel: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_monthly_reset_uses_leveling_transaction():
    """月間ランキング集計後の削除は leveling transaction の排他制御経由で行う。"""
    # 機能要件：delete_data=True の月間ランキング集計は月次データを削除する。
    # 非機能要件：削除は個別 repository 直呼びではなく LevelingTransactions の reset 経由で行う。
    # Given
    bot = _MonthlyBot()

    # When
    result = await run_monthly_ranking(cast(Any, bot), force=True, delete_data=True)

    # Then
    assert result == 0
    assert bot.db.leveling.reset_count == 1

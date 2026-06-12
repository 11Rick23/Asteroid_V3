from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot
from app.database.repositories.monthly_powers import MonthlyPowerRankingData
from app.features.leveling.commands import admin_command
from app.features.leveling.commands.admin_command import admin_power_group, aggregate_power_ranking
from app.features.leveling.monthly import build_monthly_ranking_views, run_monthly_ranking


class FakeAvatar:
    def __init__(self, user_id: int) -> None:
        self.url = f"https://example.com/avatar-{user_id}.png"


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.display_name = f"User {user_id}"
        self.display_avatar = FakeAvatar(user_id)


class FakeBot:
    def __init__(self) -> None:
        self.users = {user_id: FakeUser(user_id) for user_id in range(1, 11)}

    def get_user(self, user_id: int) -> FakeUser | None:
        return self.users.get(user_id)


class FakeMonthlyPowers:
    def __init__(self, rankings: list[MonthlyPowerRankingData]) -> None:
        self.rankings = rankings
        self.truncate_count = 0

    async def get_monthly_power_ranking(self, *, limit: int) -> list[MonthlyPowerRankingData]:
        return self.rankings[:limit]

    async def truncate_table(self) -> None:
        self.truncate_count += 1


class FakeMonthlyActionPowers:
    def __init__(self) -> None:
        self.truncate_count = 0

    async def truncate_table(self) -> None:
        self.truncate_count += 1


class FakeVoiceXPLimits:
    def __init__(self) -> None:
        self.reset_count = 0

    async def reset_voice_power(self) -> None:
        self.reset_count += 1


class FakeGuild:
    id = 100

    def get_role(self, role_id: int) -> None:
        return None

    def get_member(self, user_id: int) -> None:
        return None


class FakeResponse:
    def __init__(self) -> None:
        self.defer_calls: list[dict[str, Any]] = []

    async def defer(self, **kwargs: Any) -> None:
        self.defer_calls.append(kwargs)


class FakeFollowup:
    def __init__(self) -> None:
        self.send_calls: list[tuple[str, bool]] = []

    async def send(self, content: str, *, ephemeral: bool) -> None:
        self.send_calls.append((content, ephemeral))


def text_contents(item: Any) -> str:
    return "\n".join(child.content for child in item.walk_children() if isinstance(child, discord.ui.TextDisplay))


def test_build_monthly_ranking_views_splits_top10_into_three_messages() -> None:
    now = datetime.now()
    monthly_powers = [
        MonthlyPowerRankingData(user_id, 100, 50, 25, now, now, ranking)
        for ranking, user_id in enumerate(range(1, 11), start=1)
    ]

    views = build_monthly_ranking_views(cast(AsteroidBot, FakeBot()), monthly_powers)

    assert len(views) == 3
    assert "# 月間ランキング発表" in text_contents(views[0])
    assert len(views[0].children) == 1
    assert cast(discord.ui.Container, views[0].children[0]).accent_colour == AsteroidColor.SUCCESS

    assert "# 月間ランキング 1〜5位" in text_contents(views[1])
    assert "### 5位: User 5" in text_contents(views[1])
    assert "# 月間ランキング 6〜10位" in text_contents(views[2])
    assert "### 10位: User 10" in text_contents(views[2])
    assert sum(isinstance(child, discord.ui.Section) for child in views[1].walk_children()) == 5
    assert sum(isinstance(child, discord.ui.Section) for child in views[2].walk_children()) == 5


def test_build_monthly_ranking_views_keeps_empty_second_half_message() -> None:
    now = datetime.now()
    monthly_powers = [
        MonthlyPowerRankingData(user_id, 100, 50, 25, now, now, ranking)
        for ranking, user_id in enumerate(range(1, 4), start=1)
    ]

    views = build_monthly_ranking_views(cast(AsteroidBot, FakeBot()), monthly_powers)

    assert len(views) == 3
    assert "ランキングデータはありません。" in text_contents(views[2])


@pytest.mark.asyncio
@pytest.mark.parametrize("delete_data", [False, True])
async def test_run_monthly_ranking_deletes_data_only_when_requested(delete_data: bool) -> None:
    monthly_powers = FakeMonthlyPowers([])
    monthly_action_powers = FakeMonthlyActionPowers()
    voice_xp_limits = FakeVoiceXPLimits()
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            db=SimpleNamespace(
                is_initialized=lambda: True,
                monthly_powers=monthly_powers,
                monthly_action_powers=monthly_action_powers,
                voice_xp_limits=voice_xp_limits,
            ),
            config=SimpleNamespace(
                discord=SimpleNamespace(guild_id=100),
                leveling=SimpleNamespace(
                    top1_role_id=0,
                    top10_role_id=0,
                    month_ranking_board_channel_id=0,
                    action_power_channel_id=0,
                ),
            ),
            get_guild=lambda guild_id: FakeGuild(),
            get_channel=lambda channel_id: None,
        ),
    )

    result = await run_monthly_ranking(bot, force=True, delete_data=delete_data)

    assert result == 0
    expected_count = int(delete_data)
    assert monthly_powers.truncate_count == expected_count
    assert monthly_action_powers.truncate_count == expected_count
    assert voice_xp_limits.reset_count == expected_count


def test_power_admin_group_replaces_reset_with_aggregate_command() -> None:
    assert admin_power_group.get_command("reset_ranking") is None
    assert admin_power_group.get_command("aggregate") is aggregate_power_ranking


@pytest.mark.asyncio
async def test_aggregate_power_ranking_defaults_to_preserving_data(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[bool, bool]] = []

    async def fake_run_monthly_ranking(
        bot: AsteroidBot,
        *,
        force: bool,
        delete_data: bool,
    ) -> int:
        calls.append((force, delete_data))
        return 7

    monkeypatch.setattr(admin_command, "run_monthly_ranking", fake_run_monthly_ranking)
    response = FakeResponse()
    followup = FakeFollowup()
    interaction = SimpleNamespace(
        client=object(),
        response=response,
        followup=followup,
        guild_id=100,
        channel_id=200,
        user=SimpleNamespace(id=300),
    )

    await cast(Any, aggregate_power_ranking.callback)(cast(discord.Interaction, interaction), False)

    assert calls == [(True, False)]
    assert aggregate_power_ranking.parameters[0].default is False
    assert response.defer_calls == [{"ephemeral": True}]
    assert followup.send_calls == [
        (
            "現在のデータで月間ランキングを集計しました。対象者: 7人\n集計後のデータ削除: 未実行",
            True,
        )
    ]

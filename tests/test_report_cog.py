from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.report.cog import ReportCog


class DummyResponse:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.calls.append((content, ephemeral))


class DummyGuild:
    id = 10

    def get_channel(self, channel_id: int) -> None:
        return None


class DummyInteraction:
    def __init__(self) -> None:
        self.guild = DummyGuild()
        self.channel_id = 20
        self.user = SimpleNamespace(id=30)
        self.response = DummyResponse()
        self.edited_content: str | None = None

    async def edit_original_response(self, *, content: str) -> None:
        self.edited_content = content


@pytest.mark.asyncio
async def test_report_logs_warning_when_destination_channel_missing(caplog: pytest.LogCaptureFixture) -> None:
    bot = SimpleNamespace(
        config=SimpleNamespace(report=SimpleNamespace(report_receive_channel_id=999, report_ping_role_id=0))
    )
    cog = ReportCog(cast(AsteroidBot, bot))
    interaction = DummyInteraction()
    violator = SimpleNamespace(id=40)

    with caplog.at_level(logging.DEBUG, logger="app.features.report.cog"):
        await cast(Any, ReportCog.report.callback)(
            cog,
            cast(discord.Interaction, interaction),
            cast(discord.User, violator),
            "rule violation",
        )

    assert "レポートを送信しました: command=/report" in caplog.text
    assert "レポート送信先チャンネルが見つかりませんでした: guild_id=10 reporter_id=30 channel_id=999" in caplog.text
    assert interaction.edited_content == "レポート送信先チャンネルが見つかりませんでした。"

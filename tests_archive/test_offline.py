from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.common.offline import (
    ApplicationInfoProvider,
    OfflineInfo,
    build_offline_embed,
    build_offline_view,
    get_emergency_contact_mentions,
)


class FakeApplicationInfoProvider:
    def __init__(self, application_info: object) -> None:
        self._application_info = application_info

    async def application_info(self) -> discord.AppInfo:
        return cast(discord.AppInfo, self._application_info)


def test_build_offline_embed_displays_all_information() -> None:
    updated_at = datetime(2026, 6, 12, 12, 34, tzinfo=UTC)
    embed = build_offline_embed(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
        "認証システムは現在利用できません。",
        ("<@100>", "<@200>"),
        updated_at=updated_at,
    )

    assert embed.title == "BOT は現在オフラインです"
    assert embed.description == "認証システムは現在利用できません。"
    assert embed.fields[0].name == "理由"
    assert embed.fields[0].value == "メンテナンス"
    assert embed.fields[1].name == "予定期間"
    assert embed.fields[1].value == "1時間"
    assert embed.fields[2].name == "緊急連絡先"
    assert embed.fields[2].value == "<@100>\n<@200>"
    assert embed.fields[3].name == "最終更新日時"
    assert embed.fields[3].value == discord.utils.format_dt(updated_at, style="F")
    assert all(field.inline for field in embed.fields)


def test_build_offline_view_displays_all_information() -> None:
    updated_at = datetime(2026, 6, 12, 12, 34, tzinfo=UTC)

    view = build_offline_view(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
        "認証システムは現在利用できません。",
        ("<@100>", "<@200>"),
        updated_at=updated_at,
    )

    assert view.has_components_v2()
    container = cast(discord.ui.Container, view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0]).content
    assert container.accent_color == 0xD12121
    assert "# BOT は現在オフラインです" in text
    assert "認証システムは現在利用できません。" in text
    assert "**理由**\nメンテナンス" in text
    assert "**予定期間**\n1時間" in text
    assert "**緊急連絡先**\n<@100>\n<@200>" in text
    assert discord.utils.format_dt(updated_at, style="F") in text


@pytest.mark.asyncio
async def test_get_emergency_contact_mentions_uses_application_owner() -> None:
    provider = FakeApplicationInfoProvider(
        SimpleNamespace(
            owner=SimpleNamespace(mention="<@100>"),
            team=None,
        )
    )

    mentions = await get_emergency_contact_mentions(cast(ApplicationInfoProvider, provider))

    assert mentions == ("<@100>",)


@pytest.mark.asyncio
async def test_get_emergency_contact_mentions_uses_all_team_members() -> None:
    provider = FakeApplicationInfoProvider(
        SimpleNamespace(
            owner=SimpleNamespace(mention="<@100>"),
            team=SimpleNamespace(
                members=[
                    SimpleNamespace(mention="<@100>"),
                    SimpleNamespace(mention="<@200>"),
                ]
            ),
        )
    )

    mentions = await get_emergency_contact_mentions(cast(ApplicationInfoProvider, provider))

    assert mentions == ("<@100>", "<@200>")

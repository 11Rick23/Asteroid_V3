from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.common.offline import (
    ApplicationInfoProvider,
    OfflineInfo,
    build_offline_embed,
    get_emergency_contact_mentions,
)


class FakeApplicationInfoProvider:
    def __init__(self, application_info: object) -> None:
        self._application_info = application_info

    async def application_info(self) -> discord.AppInfo:
        return cast(discord.AppInfo, self._application_info)


def test_build_offline_embed_displays_all_information() -> None:
    embed = build_offline_embed(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
        ("<@100>", "<@200>"),
    )

    assert embed.title == "BOT は現在オフラインです"
    assert embed.fields[0].name == "理由"
    assert embed.fields[0].value == "メンテナンス"
    assert embed.fields[1].name == "予定期間"
    assert embed.fields[1].value == "1時間"
    assert embed.fields[2].name == "緊急連絡先"
    assert embed.fields[2].value == "<@100>\n<@200>"


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

from __future__ import annotations

from typing import cast

import pytest
from discord import Interaction

from app.common.guild_scope import (
    OUTSIDE_OPERATING_GUILD_MESSAGE,
    GuildScopedView,
    OperatingGuildCommandTree,
    OutsideOperatingGuild,
    is_operating_guild_id,
    send_outside_operating_guild_message,
)
from tests.support.discord_fakes import FakeClient, FakeInteraction, FakeInteractionResponse


def test_checks_guild_id(operating_guild_id):
    """運用対象 guild ID だけを許可し、DM と対象外 guild は拒否する。"""
    # Given
    client = FakeClient(operating_guild_id)

    # When / Then
    assert is_operating_guild_id(client, operating_guild_id) is True
    assert is_operating_guild_id(client, operating_guild_id + 1) is False
    assert is_operating_guild_id(client, None) is False


@pytest.mark.asyncio
async def test_sends_initial_denial(operating_guild_id):
    """未応答 interaction では対象外 guild の拒否通知を ephemeral response として送信する。"""
    # Given
    interaction = FakeInteraction(client=FakeClient(operating_guild_id), guild_id=None)

    # When
    await send_outside_operating_guild_message(cast(Interaction, interaction))

    # Then
    assert interaction.response.sent_messages == [
        {"content": OUTSIDE_OPERATING_GUILD_MESSAGE, "ephemeral": True},
    ]
    assert interaction.followup.sent_messages == []


@pytest.mark.asyncio
async def test_sends_followup_denial(operating_guild_id):
    """応答済み interaction では対象外 guild の拒否通知を ephemeral followup として送信する。"""
    # Given
    interaction = FakeInteraction(
        client=FakeClient(operating_guild_id),
        guild_id=None,
        response=FakeInteractionResponse(done=True),
    )

    # When
    await send_outside_operating_guild_message(cast(Interaction, interaction))

    # Then
    assert interaction.response.sent_messages == []
    assert interaction.followup.sent_messages == [
        {"content": OUTSIDE_OPERATING_GUILD_MESSAGE, "ephemeral": True},
    ]


@pytest.mark.asyncio
async def test_tree_rejects_outside(operating_guild_id):
    """CommandTree は対象外 guild の slash command 実行を CheckFailure として拒否する。"""
    # Given
    tree = object.__new__(OperatingGuildCommandTree)
    tree.client = FakeClient(operating_guild_id)
    interaction = FakeInteraction(client=tree.client, guild_id=operating_guild_id + 1)

    # When / Then
    with pytest.raises(OutsideOperatingGuild):
        await tree.interaction_check(cast(Interaction, interaction))


@pytest.mark.asyncio
async def test_view_rejects_outside(operating_guild_id):
    """GuildScopedView は対象外 guild の UI 操作を拒否し、ephemeral 通知を返す。"""
    # Given
    view = GuildScopedView()
    interaction = FakeInteraction(client=FakeClient(operating_guild_id), guild_id=operating_guild_id + 1)

    # When
    allowed = await view.interaction_check(cast(Interaction, interaction))

    # Then
    assert allowed is False
    assert interaction.response.sent_messages == [
        {"content": OUTSIDE_OPERATING_GUILD_MESSAGE, "ephemeral": True},
    ]

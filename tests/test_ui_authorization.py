from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.report.views import ReportResolveView
from app.features.rolepanel.admin_views import RolePanelAdminRoleSelect
from app.features.vc import service as vc_service
from app.features.vc.service import VoiceCreateService
from app.features.vc.views import TogglePrivacyButton


class FakeResponse:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.edit_calls: list[dict[str, object]] = []
        self.defer_calls: list[dict[str, object]] = []

    def is_done(self) -> bool:
        return False

    async def send_message(
        self,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        ephemeral: bool = False,
    ) -> None:
        self.messages.append({"content": content, "embed": embed, "ephemeral": ephemeral})

    async def edit_message(self, **kwargs: object) -> None:
        self.edit_calls.append(kwargs)

    async def defer(self, *, thinking: bool = False) -> None:
        self.defer_calls.append({"thinking": thinking})


class FakeRolePanelRepository:
    def __init__(self) -> None:
        self.set_roles_calls: list[tuple[int, list[int]]] = []

    async def set_roles(self, category_id: int, role_ids: list[int]) -> None:
        self.set_roles_calls.append((category_id, role_ids))


@pytest.mark.asyncio
async def test_report_resolve_rejects_non_administrator() -> None:
    view = ReportResolveView()
    response = FakeResponse()
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=10),
        response=response,
        message=SimpleNamespace(id=20, embeds=[discord.Embed()]),
        guild_id=30,
        channel_id=40,
    )

    await cast(Any, view.children[0]).callback(cast(discord.Interaction, interaction))

    assert response.messages == [
        {"content": "この操作を実行する権限がありません。", "embed": None, "ephemeral": True}
    ]
    assert response.edit_calls == []


@pytest.mark.asyncio
async def test_rolepanel_admin_select_rejects_non_owner_without_admin_permission() -> None:
    repository = FakeRolePanelRepository()
    bot = SimpleNamespace(db=SimpleNamespace(role_panel=repository))
    response = FakeResponse()
    interaction = SimpleNamespace(
        client=bot,
        user=SimpleNamespace(id=10),
        response=response,
        guild_id=20,
    )

    async def on_update() -> None:
        raise AssertionError("unauthorized interaction must not refresh the panel")

    select = RolePanelAdminRoleSelect(category_id=30, role_ids=[], actor_id=40, on_update=on_update)

    await select.callback(cast(discord.Interaction, interaction))

    assert repository.set_roles_calls == []
    assert len(response.messages) == 1
    assert response.messages[0]["ephemeral"] is True
    embed = response.messages[0]["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.title == "権限がありません"


class FakeMember:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeVoiceChannel:
    def __init__(self) -> None:
        self.id = 100
        self.guild = SimpleNamespace(id=200)

    def permissions_for(self, _: FakeMember) -> SimpleNamespace:
        return SimpleNamespace(manage_channels=False)


@pytest.mark.asyncio
async def test_voice_channel_management_rejects_member_without_manage_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vc_service.discord, "Member", FakeMember)
    monkeypatch.setattr(vc_service.discord, "VoiceChannel", FakeVoiceChannel)
    service = VoiceCreateService(
        cast(
            AsteroidBot,
            SimpleNamespace(config=SimpleNamespace(vc=SimpleNamespace(voice_create_channel_id=999))),
        )
    )
    response = FakeResponse()
    member = FakeMember(10)
    channel = FakeVoiceChannel()
    interaction = SimpleNamespace(
        guild=None,
        channel=channel,
        channel_id=channel.id,
        user=member,
        response=response,
    )

    result = await service.ensure_voice_channel(
        cast(discord.Interaction, interaction),
        require_manage=True,
    )

    assert result is None
    assert response.messages == [{"content": "VCの管理権限がありません。", "embed": None, "ephemeral": False}]


class RejectingVoiceService:
    def __init__(self) -> None:
        self.ensure_calls: list[dict[str, object]] = []
        self.set_private_called = False

    async def ensure_voice_channel(self, _: object, **kwargs: object) -> None:
        self.ensure_calls.append(kwargs)
        return None

    async def set_private(self, *_: object) -> None:
        self.set_private_called = True


@pytest.mark.asyncio
async def test_voice_privacy_button_requires_manage_permission_before_mutation() -> None:
    service = RejectingVoiceService()
    response = FakeResponse()
    interaction = SimpleNamespace(response=response, user=SimpleNamespace(id=10))
    button = TogglePrivacyButton(cast(VoiceCreateService, service))

    await button.callback(cast(discord.Interaction, interaction))

    assert response.defer_calls == [{"thinking": True}]
    assert service.ensure_calls == [{"require_manage": True, "expected_channel_id": None}]
    assert service.set_private_called is False

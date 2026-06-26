from __future__ import annotations

from typing import Any, cast

import pytest

from app.features.rolepanel.runtime import RolePanelCog
from tests.support.discord_fakes import FakeGuild, FakeMember


class _Bot:
    def __init__(self, *, operating: bool = True) -> None:
        self.operating = operating

    def is_operating_guild(self, _guild: object) -> bool:
        return self.operating


class _Service:
    def __init__(self) -> None:
        self.removed_members: list[object] = []

    async def remove_boost_required_roles(self, member: object) -> None:
        self.removed_members.append(member)


def _cog(*, operating: bool = True) -> tuple[RolePanelCog, _Service]:
    cog = object.__new__(RolePanelCog)
    cog.bot = cast(Any, _Bot(operating=operating))
    service = _Service()
    cog.service = cast(Any, service)
    return cog, service


@pytest.mark.asyncio
async def test_removes_roles_on_boost_loss():
    """ブースト解除時はブースト必須カテゴリのロール削除処理を呼び出す。"""
    # 機能要件：ブースト解除時は対象 member のブースト必須ロール削除処理を実行する。
    # Given
    guild = FakeGuild()
    before = FakeMember(guild=guild, premium_since=object())
    after = FakeMember(guild=guild, premium_since=None)
    cog, service = _cog()

    # When
    await cog.on_member_update(cast(Any, before), cast(Any, after))

    # Then
    assert service.removed_members == [after]


@pytest.mark.asyncio
async def test_skips_outside_guild():
    """対象外 guild の member update ではブースト解除処理を行わない。"""
    # 非機能要件：対象外 guild の member update ではロール削除処理を実行しない。
    # Given
    guild = FakeGuild()
    before = FakeMember(guild=guild, premium_since=object())
    after = FakeMember(guild=guild, premium_since=None)
    cog, service = _cog(operating=False)

    # When
    await cog.on_member_update(cast(Any, before), cast(Any, after))

    # Then
    assert service.removed_members == []


@pytest.mark.asyncio
async def test_skips_without_boost_loss():
    """ブースト解除以外の member update ではロール削除処理を行わない。"""
    # 非機能要件：ブースト状態が解除されていない更新ではロール削除処理を実行しない。
    # Given
    guild = FakeGuild()
    before = FakeMember(guild=guild, premium_since=None)
    after = FakeMember(guild=guild, premium_since=object())
    cog, service = _cog()

    # When
    await cog.on_member_update(cast(Any, before), cast(Any, after))

    # Then
    assert service.removed_members == []

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from app.core.config import GradeRoleReward
from app.features.leveling.commands.admin_groups import admin_power_group, admin_shard_group
from app.features.leveling.commands.set_command import register_set_commands, set_powers, set_shards
from app.features.leveling.manage_reward_role import get_member_grade_roles


def test_registers_set_commands():
    """set コマンドは既存の管理者用グループ配下に日本語引数で登録する。"""
    # 機能要件：シャードとパワーを設定するコマンドを追加する。
    # 非機能要件：管理者チェックを持ち、登録を重複させない。
    # Given / When
    register_set_commands()
    register_set_commands()
    # Then
    for group, command in [(admin_shard_group, set_shards), (admin_power_group, set_powers)]:
        assert group.get_command("set") is command
        assert command.checks
        assert command.default_permissions and command.default_permissions.administrator
        assert all(parameter.description != "…" for parameter in command.parameters)
        assert all(parameter.min_value == 0 for parameter in command.parameters[1:])


@pytest.mark.asyncio
@pytest.mark.parametrize("command", [set_shards, set_powers])
async def test_rejects_negative_set(command):
    """負数の set 要求では保存処理を呼ばない。"""
    # 非機能要件：不正入力時には DB を参照する前に拒否する。
    # Given
    interaction = SimpleNamespace(response=SimpleNamespace(send_message=AsyncMock()))
    # When
    await cast(Any, command.callback)(interaction, SimpleNamespace(id=1), -1, 0, 0)
    # Then
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


def test_zero_grade_without_base_reward():
    """最初の報酬グレード未満に戻してもロール同期が失敗しない。"""
    # 機能要件：0への復元では該当報酬がなければ全て剥奪対象とする。
    # Given / When / Then
    assert get_member_grade_roles(0, [GradeRoleReward(grade=1, role_id=10)], False) == ([], [10])

from __future__ import annotations

from app.core.config import GradeRoleReward, PrestigeRoleReward
from app.features.leveling.manage_reward_role import get_member_grade_roles, get_member_prestige_roles


def test_selects_grade_role():
    """stack 無効時は到達済みの最上位 grade role だけを付与対象にする。"""
    # 機能要件：stack 無効の grade 報酬では到達済みの最上位ロールだけを付与対象にする。
    # Given
    rewards = [
        GradeRoleReward(grade=0, role_id=10),
        GradeRoleReward(grade=5, role_id=20),
        GradeRoleReward(grade=10, role_id=30),
    ]

    # When
    add_roles, remove_roles = get_member_grade_roles(7, rewards, stack=False)

    # Then
    assert add_roles == [20]
    assert remove_roles == [10, 30]


def test_stacks_prestige_roles():
    """stack 有効時は到達済み prestige role をすべて付与対象にする。"""
    # 機能要件：stack 有効の prestige 報酬では到達済みロールをすべて付与対象にする。
    # Given
    rewards = [
        PrestigeRoleReward(prestige=1, role_id=10),
        PrestigeRoleReward(prestige=2, role_id=20),
        PrestigeRoleReward(prestige=3, role_id=30),
    ]

    # When
    add_roles, remove_roles = get_member_prestige_roles(2, rewards, stack=True)

    # Then
    assert add_roles == [10, 20]
    assert remove_roles == [30]

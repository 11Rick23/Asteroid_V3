from __future__ import annotations

from app.features.leveling.commands.admin_command import leveling_admin_group
from app.features.leveling.commands.command import transfer_mee6


def test_admin_group_is_admin_only():
    """管理者用レベリング group は guild 限定で管理者権限をデフォルト権限にする。"""
    # 非機能要件：レベリング管理 group は guild 限定かつ管理者向け権限で公開される。
    # Given / When / Then
    assert leveling_admin_group.name == "leveling"
    assert leveling_admin_group.guild_only is True
    assert leveling_admin_group.default_permissions is not None
    assert leveling_admin_group.default_permissions.administrator is True


def test_transfer_mee6_metadata():
    """MEE6 移行 setup command は guild 限定で日本語引数を公開する。"""
    # 機能要件：MEE6 移行 command はロール同期とプレステージ通知の指定を公開する。
    # 非機能要件：MEE6 移行 command は guild 限定かつ管理者向け command として登録する。
    # Given / When / Then
    assert transfer_mee6.guild_only is True
    assert transfer_mee6.default_permissions is not None
    assert transfer_mee6.default_permissions.administrator is True
    assert [parameter.display_name for parameter in transfer_mee6.parameters] == ["ロール同期", "プレステージ通知"]

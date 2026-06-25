from __future__ import annotations

import pytest
from ruamel.yaml import YAML

from app.core.config import AsteroidConfig


def test_loads_minimal(tmp_path):
    """最小限の設定ファイルでは不足項目を安全なデフォルトで補完する。"""
    # 機能要件：最小設定でも AsteroidConfig を読み込める。
    # 非機能要件：未設定項目は安全なデフォルト値で補完される。
    # Given
    config_path = tmp_path / "config.yaml"
    config_path.write_text("discord:\n  guild_id: 123\n", encoding="utf-8")

    # When
    config = AsteroidConfig.load(config_path)

    # Then
    assert config.discord.guild_id == 123
    assert config.discord.sync_commands_on_startup is True
    assert config.features.rolepanel is True
    assert config.database.url == ""


def test_rejects_unknown_key(tmp_path):
    """未知の設定キーが含まれる場合は設定読み込みを失敗させる。"""
    # 非機能要件：未知の設定キーを無視せず、起動前に設定ミスとして失敗させる。
    # Given
    config_path = tmp_path / "config.yaml"
    config_path.write_text("discord:\n  guild_id: 123\nunknown: true\n", encoding="utf-8")

    # When / Then
    with pytest.raises(RuntimeError, match="設定の読み込みに失敗しました"):
        AsteroidConfig.load(config_path)


def test_example_is_valid():
    """config.example.yaml は AsteroidConfig として読み込める構造を保つ。"""
    # 機能要件：配布用設定例は現在の設定 schema として読み込める。
    # Given
    yaml = YAML(typ="safe")

    # When
    with open("config.example.yaml", encoding="utf-8") as file:
        data = yaml.load(file)
    config = AsteroidConfig.model_validate(data)

    # Then
    assert config.database.url.startswith("mysql+aiomysql://")
    assert config.discord.register_globally is False
    assert config.auth.panel_channel_id == 0

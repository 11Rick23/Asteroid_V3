from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import AsteroidConfig


def test_config_loads_nested_sections(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
discord:
  token: "token"
  guild_id: 1
logging:
  level: "DEBUG"
permission_roles_id_list:
  admin: 321
report:
  report_receive_channel_id: 999
  report_ping_role_id: 123
leveling:
  message_cooldown: 30
""",
        encoding="utf-8",
    )

    config = AsteroidConfig.load(config_file)

    assert config.discord.token == "token"
    assert config.discord.guild_id == 1
    assert config.logging.level == "DEBUG"
    assert config.permission_roles_id_list.admin == 321
    assert config.report.report_receive_channel_id == 999
    assert config.report.report_ping_role_id == 123
    assert config.leveling.message_cooldown == 30
    assert config.leveling.action_power_channel_id == 0
    assert config.auth.panel_channel_id == 0
    assert config.rolepanel.panel_channel_id == 0


def test_config_provides_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
vc:
  voice_create_channel_id: 123456789
""",
        encoding="utf-8",
    )

    config = AsteroidConfig.load(config_file)

    assert config.discord.guild_id == 0
    assert config.vc.voice_create_channel_id == 123456789
    assert config.free_category.free_category_channel_limit == 20
    assert config.log.main_log_channel_id == 0
    assert config.punish.punishment_board_channel_id == 0
    assert config.permission_roles_id_list.admin == 0
    assert config.report.report_ping_role_id == 0
    assert config.leveling.action_power_channel_id == 0
    assert config.auth.panel_channel_id == 0
    assert config.rolepanel.panel_channel_id == 0


def test_permission_roles_enabled_role_ids_ignores_zero_values(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
permission_roles_id_list:
  admin: 1
  manage_member: 0
  extra: 2
""",
        encoding="utf-8",
    )

    config = AsteroidConfig.load(config_file)

    assert config.permission_roles_id_list.enabled_role_ids() == [1, 2]


def test_config_rejects_legacy_guild_ids(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
discord:
  guild_ids: [1]
""",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="guild_ids"):
        AsteroidConfig.load(config_file)

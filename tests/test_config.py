from __future__ import annotations

from pathlib import Path

from app.core.config import AsteroidConfig


def test_config_loads_nested_and_legacy_keys(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
discord:
  token: "token"
  guild_ids: [1, 2]
logging:
  debug_log_retention_days: 10
leveling:
  settings:
    message_cooldown: 30
""",
        encoding="utf-8",
    )

    config = AsteroidConfig.load(config_file)

    assert config.discord.token == "token"
    assert config["guild_id_list"] == [1, 2]
    assert config["DEBUG_LOG_RETENTION_DAYS"] == 10
    assert config["message_cooldown"] == 30


def test_config_provides_defaults_and_vc_alias(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
vc:
  settings:
    create_vc_join_channel_id: 123456789
""",
        encoding="utf-8",
    )

    config = AsteroidConfig.load(config_file)

    assert config["voice_create_channel_id"] == 123456789
    assert config["create_vc_join_channel_id"] == 123456789
    assert config["free_category_channel_limit"] == 20
    assert config["main_log_channel_id"] == 0

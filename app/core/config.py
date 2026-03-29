from __future__ import annotations

from functools import cached_property
from logging import getLogger
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML

logger = getLogger("asteroid.config")

_config: AsteroidConfig | None = None

_SECTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "log": {
        "main_log_channel_id": 0,
    },
    "auth": {
        "unauthorized_role_id": 0,
        "welcome_channel_id": 0,
    },
    "birthday": {
        "birthday_channel_id": 0,
        "birthday_role_id": 0,
    },
    "moderation": {
        "punishment_board_channel_id": 0,
        "report_receive_channel_id": 0,
        "admin_perms_role_id": 0,
        "member_manage_perms_role_id": 0,
        "role_manage_perms_role_id": 0,
        "channel_manage_perms_role_id": 0,
        "message_manage_perms_role_id": 0,
        "emoji_manage_perms_role_id": 0,
        "log_view_perms_role_id": 0,
        "event_create_perms_role_id": 0,
        "thread_create_perms_role_id": 0,
        "crime_record_role_id_list": [],
        "forbid_role_id": 0,
        "mute_role_id": 0,
    },
    "leveling": {
        "message_cooldown": 15,
        "min_xp_per_message": 10,
        "max_xp_per_message": 25,
        "min_xp_per_voice_minute": 10,
        "max_xp_per_voice_minute": 25,
        "voice_xp_limit": 300,
        "voice_xp_adjust": 0.3,
        "stack_grade_role": False,
        "stack_prestige_role": True,
        "grade_roles_id_list": [],
        "prestige_roles_id_list": [],
        "prestige_announce_channel_id_list": [],
        "ranking_board_channel_id_list": [],
        "month_ranking_board_channel_id_list": [],
        "top1_role_id": 0,
        "top10_role_id": 0,
        "true_top_ranker_role_id": 0,
    },
    "starboard": {
        "starboard_channel_id": 0,
    },
    "vc": {
        "voice_create_channel_id": 0,
        "create_vc_join_channel_id": 0,
        "voice_category_id": 0,
    },
    "free_category": {
        "hall_of_fame_category_id": 0,
        "free_category_id": 0,
        "minor_category_id": 0,
        "fc_archive_category_id": 0,
        "side_button_channel_id": 0,
        "text_create_channel_id": 0,
        "hall_of_fame_channel_limit": 5,
        "free_category_channel_limit": 20,
        "minor_category_channel_limit": 15,
        "text_create_channel_cooldown_seconds": 86400,
        "bump_cooldown_seconds": 30,
        "bump_cooldown_seconds_after_bump": 900,
        "hall_of_fame_bump_chance": 0.01,
        "free_category_bump_chance": 0.05,
        "minor_category_bump_chance": 1.0,
        "category_move_chance": 0.25,
    },
    "roles": {
        "join_role_id_list": [],
        "bot_join_role_id_list": [],
        "ignored_save_role_id_list": [],
    },
    "suggest": {
        "suggestion_forum_channel_id": 0,
    },
    "bump_notifier": {},
    "link_expander": {},
}


def _clone_value(value: Any) -> Any:
    if isinstance(value, list | dict):
        return value.copy()
    return value


class BaseSection(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LoggingConfig(BaseSection):
    level: str = "INFO"
    debug_log_retention_days: int = 7
    warning_log_retention_days: int = 7


class DiscordConfig(BaseSection):
    token: str = ""
    guild_ids: list[int] = Field(default_factory=list)
    sync_commands_on_startup: bool = True
    register_globally: bool = False
    activity_name: str = "ナメック星"
    status: str = "dnd"


class DatabaseConfig(BaseSection):
    url: str = ""
    echo: bool = False


class FeatureFlags(BaseSection):
    auth: bool = True
    log_login: bool = True
    log_error: bool = True
    roles: bool = True
    suggest: bool = True
    bump_notifier: bool = True
    birthday: bool = True
    link_expander: bool = True
    moderation_report: bool = True
    moderation_punish: bool = True
    starboard: bool = True
    free_category: bool = True
    vc: bool = True
    leveling_core: bool = True
    leveling_command: bool = True
    leveling_power: bool = True
    leveling_shard: bool = True
    leveling_admin: bool = True


class FeatureConfig(BaseSection):
    settings: dict[str, Any] = Field(default_factory=dict)


class AsteroidConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    log: FeatureConfig = Field(default_factory=FeatureConfig)
    auth: FeatureConfig = Field(default_factory=FeatureConfig)
    birthday: FeatureConfig = Field(default_factory=FeatureConfig)
    moderation: FeatureConfig = Field(default_factory=FeatureConfig)
    leveling: FeatureConfig = Field(default_factory=FeatureConfig)
    starboard: FeatureConfig = Field(default_factory=FeatureConfig)
    vc: FeatureConfig = Field(default_factory=FeatureConfig)
    free_category: FeatureConfig = Field(default_factory=FeatureConfig)
    roles: FeatureConfig = Field(default_factory=FeatureConfig)
    suggest: FeatureConfig = Field(default_factory=FeatureConfig)
    bump_notifier: FeatureConfig = Field(default_factory=FeatureConfig)
    link_expander: FeatureConfig = Field(default_factory=FeatureConfig)
    legacy: dict[str, Any] = Field(default_factory=dict)

    @cached_property
    def _legacy_index(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for defaults in _SECTION_DEFAULTS.values():
            for key, value in defaults.items():
                result[key] = _clone_value(value)

        if self.model_extra:
            result.update(self.model_extra)

        result.update(self.legacy)
        result.update(
            {
                "guild_id_list": self.discord.guild_ids,
                "sync_slash_commands_on_startup": self.discord.sync_commands_on_startup,
                "register_slash_commands_globally": self.discord.register_globally,
                "DEBUG_LOG_RETENTION_DAYS": self.logging.debug_log_retention_days,
                "WARNING_LOG_RETENTION_DAYS": self.logging.warning_log_retention_days,
            }
        )
        for section_name in (
            "log",
            "auth",
            "birthday",
            "moderation",
            "leveling",
            "starboard",
            "vc",
            "free_category",
            "roles",
            "suggest",
            "bump_notifier",
            "link_expander",
        ):
            section: FeatureConfig = getattr(self, section_name)
            result.update({key: _clone_value(value) for key, value in _SECTION_DEFAULTS.get(section_name, {}).items()})
            result.update(section.settings)

        voice_create_channel_id = int(
            result.get("voice_create_channel_id") or result.get("create_vc_join_channel_id") or 0
        )
        result["voice_create_channel_id"] = voice_create_channel_id
        result["create_vc_join_channel_id"] = voice_create_channel_id
        return result

    def __getitem__(self, key: str) -> Any:
        if key in self._legacy_index:
            return self._legacy_index[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self._legacy_index.get(key, default)

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> AsteroidConfig:
        logger.debug("設定を読み込みます。")
        yaml = YAML(typ="safe")
        with Path(path).open(encoding="utf-8") as f:
            yaml_data = yaml.load(f) or {}
        try:
            return cls.model_validate(dict(yaml_data))
        except ValidationError as exc:
            logger.error("設定の読み込みに失敗しました: %s", exc)
            raise RuntimeError(f"設定の読み込みに失敗しました: \n{exc}") from exc


def get_config() -> AsteroidConfig:
    global _config
    if _config is None:
        _config = AsteroidConfig.load()
    return _config


def reload_config() -> AsteroidConfig:
    global _config
    _config = AsteroidConfig.load()
    return _config

from __future__ import annotations

from logging import getLogger
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML

logger = getLogger("asteroid.config")

_config: AsteroidConfig | None = None


class BaseSection(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    report: bool = True
    punish: bool = True
    starboard: bool = True
    free_category: bool = True
    vc: bool = True
    leveling: bool = True


class GradeRoleReward(BaseSection):
    grade: int
    role_id: int


class PrestigeRoleReward(BaseSection):
    prestige: int
    role_id: int


class LogConfig(BaseSection):
    main_log_channel_id: int = 0


class AuthConfig(BaseSection):
    unauthorized_role_id: int = 0
    welcome_channel_id: int = 0
    welcome_ping_role_id: int = 0


class BirthdayConfig(BaseSection):
    birthday_channel_id: int = 0
    birthday_role_id: int = 0


class PunishConfig(BaseSection):
    punishment_board_channel_id: int = 0
    crime_record_role_id_list: list[int] = Field(default_factory=list)
    forbid_role_id: int = 0
    mute_role_id: int = 0


class PermissionRolesConfig(BaseSection):
    admin: int = 0
    manage_member: int = 0
    manage_role: int = 0
    manage_channel: int = 0
    manage_message: int = 0
    manage_emoji: int = 0
    view_log: int = 0
    create_event: int = 0
    create_thread: int = 0
    speak: int = 0
    media: int = 0
    extra: int = 0

    def enabled_role_ids(self) -> list[int]:
        return [role_id for role_id in self.model_dump().values() if role_id]


class ReportConfig(BaseSection):
    report_receive_channel_id: int = 0


class LevelingConfig(BaseSection):
    message_cooldown: int = 15
    min_xp_per_message: int = 10
    max_xp_per_message: int = 25
    min_xp_per_voice_minute: int = 10
    max_xp_per_voice_minute: int = 25
    voice_xp_limit: int = 300
    voice_xp_adjust: float = 0.3
    stack_grade_role: bool = False
    stack_prestige_role: bool = True
    grade_roles_id_list: list[GradeRoleReward] = Field(default_factory=list)
    prestige_roles_id_list: list[PrestigeRoleReward] = Field(default_factory=list)
    prestige_announce_channel_id: int = 0
    ranking_board_channel_id: int = 0
    month_ranking_board_channel_id: int = 0
    top1_role_id: int = 0
    top10_role_id: int = 0
    true_top_ranker_role_id: int = 0


class StarboardConfig(BaseSection):
    starboard_channel_id: int = 0


class VCConfig(BaseSection):
    voice_create_channel_id: int = 0
    voice_category_id: int = 0


class FreeCategoryConfig(BaseSection):
    hall_of_fame_category_id: int = 0
    free_category_id: int = 0
    minor_category_id: int = 0
    fc_archive_category_id: int = 0
    text_create_channel_id: int = 0
    hall_of_fame_channel_limit: int = 5
    free_category_channel_limit: int = 20
    minor_category_channel_limit: int = 15
    text_create_channel_cooldown_seconds: int = 86400
    bump_cooldown_seconds: int = 30
    bump_cooldown_seconds_after_bump: int = 900
    hall_of_fame_bump_chance: float = 0.01
    free_category_bump_chance: float = 0.05
    minor_category_bump_chance: float = 1.0
    category_move_chance: float = 0.25


class RolesConfig(BaseSection):
    join_role_id_list: list[int] = Field(default_factory=list)
    bot_join_role_id_list: list[int] = Field(default_factory=list)
    ignored_save_role_id_list: list[int] = Field(default_factory=list)


class SuggestConfig(BaseSection):
    suggestion_forum_channel_id: int = 0


class EmptyFeatureConfig(BaseSection):
    pass


class AsteroidConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    log: LogConfig = Field(default_factory=LogConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    birthday: BirthdayConfig = Field(default_factory=BirthdayConfig)
    punish: PunishConfig = Field(default_factory=PunishConfig)
    permission_roles_id_list: PermissionRolesConfig = Field(default_factory=PermissionRolesConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    leveling: LevelingConfig = Field(default_factory=LevelingConfig)
    starboard: StarboardConfig = Field(default_factory=StarboardConfig)
    vc: VCConfig = Field(default_factory=VCConfig)
    free_category: FreeCategoryConfig = Field(default_factory=FreeCategoryConfig)
    roles: RolesConfig = Field(default_factory=RolesConfig)
    suggest: SuggestConfig = Field(default_factory=SuggestConfig)
    bump_notifier: EmptyFeatureConfig = Field(default_factory=EmptyFeatureConfig)
    link_expander: EmptyFeatureConfig = Field(default_factory=EmptyFeatureConfig)

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

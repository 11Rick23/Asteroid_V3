from __future__ import annotations

from collections.abc import Iterator

from .config import AsteroidConfig

FEATURE_EXTENSION_MAP = (
    ("log_error", "app.features.logging.error"),
    ("log_login", "app.features.logging.login"),
    ("auth", "app.features.auth.cog"),
    ("moderation_punish", "app.features.moderation.punish"),
    ("moderation_report", "app.features.moderation.report"),
    ("vc", "app.features.vc.cog"),
    ("free_category", "app.features.free_category.cog"),
    ("roles", "app.features.roles.cog"),
    ("starboard", "app.features.starboard.cog"),
    ("link_expander", "app.features.link_expander.cog"),
    ("leveling_core", "app.features.leveling.core"),
    ("leveling_command", "app.features.leveling.commands.command"),
    ("leveling_shard", "app.features.leveling.commands.shard_command"),
    ("leveling_power", "app.features.leveling.commands.power_command"),
    ("leveling_admin", "app.features.leveling.commands.admin_command"),
    ("bump_notifier", "app.features.bump_notifier.cog"),
    ("birthday", "app.features.birthday.cog"),
    ("suggest", "app.features.suggest.cog"),
)


def iter_enabled_extensions(config: AsteroidConfig) -> Iterator[str]:
    for flag_name, extension in FEATURE_EXTENSION_MAP:
        if getattr(config.features, flag_name):
            yield extension

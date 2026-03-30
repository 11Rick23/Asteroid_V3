from __future__ import annotations

from collections.abc import Iterator
from logging import getLogger

from .config import AsteroidConfig

logger = getLogger(__name__)

# アルファベット順で記載！
FEATURE_EXTENSION_MAP = (
    ("auth", "app.features.auth.cog"),
    ("birthday", "app.features.birthday.cog"),
    ("bump_notifier", "app.features.bump_notifier.cog"),
    ("free_category", "app.features.free_category.cog"),
    ("leveling", "app.features.leveling.cog"),
    ("link_expander", "app.features.link_expander.cog"),
    ("log_error", "app.features.log.error"),
    ("log_login", "app.features.log.login"),
    ("punish", "app.features.punish.cog"),
    ("report", "app.features.report.cog"),
    ("roles", "app.features.roles.cog"),
    ("starboard", "app.features.starboard.cog"),
    ("suggest", "app.features.suggest.cog"),
    ("vc", "app.features.vc.cog"),
)


def iter_enabled_extensions(config: AsteroidConfig) -> Iterator[str]:
    for flag_name, extension in FEATURE_EXTENSION_MAP:
        enabled = getattr(config.features, flag_name)
        logger.debug(f"拡張機能の有効判定: feature={flag_name} enabled={enabled} extension={extension}")
        if enabled:
            yield extension

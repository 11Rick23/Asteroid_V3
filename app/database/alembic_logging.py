from __future__ import annotations

from logging.config import fileConfig


def configure_alembic_logging(config_file_name: str | None) -> None:
    if config_file_name is None:
        return

    fileConfig(config_file_name, disable_existing_loggers=False)

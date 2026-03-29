from __future__ import annotations

import logging
from logging import StreamHandler, getLogger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .config import AsteroidConfig


class SimpleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info and not record.exc_text:
            record.exc_text = "\n" + self.formatException(record.exc_info)
        return super().format(record)


def setup_logger(config: AsteroidConfig) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    formatter = SimpleFormatter(
        "%(asctime)-22s[%(name)s] [%(filename)s:%(lineno)d]\n%(levelname)-21s %(message)s\n",
        "[%Y-%m-%d %H:%M:%S]",
    )

    console_handler = StreamHandler()
    debug_handler = TimedRotatingFileHandler(
        filename=log_dir / "debug",
        when="midnight",
        backupCount=config.logging.debug_log_retention_days,
        encoding="utf-8",
    )
    warning_handler = TimedRotatingFileHandler(
        filename=log_dir / "warning",
        when="midnight",
        backupCount=config.logging.warning_log_retention_days,
        encoding="utf-8",
    )

    debug_handler.suffix = "_%Y-%m-%d.log"
    warning_handler.suffix = "_%Y-%m-%d.log"

    for handler in (console_handler, debug_handler, warning_handler):
        handler.setFormatter(formatter)

    console_handler.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))
    debug_handler.setLevel(logging.DEBUG)
    warning_handler.setLevel(logging.WARNING)

    root = getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    root.addHandler(console_handler)
    root.addHandler(debug_handler)
    root.addHandler(warning_handler)

    getLogger("discord").setLevel(logging.INFO)
    getLogger("asteroid").setLevel(logging.DEBUG)

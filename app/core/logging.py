from __future__ import annotations

import logging
from logging import StreamHandler, getLogger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Literal

from discord.utils import stream_supports_colour as supports_color

from .config import AsteroidConfig


def color_code_gen(
    font_color: Literal["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"] | None = None,
    bg_color: Literal["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"] | None = None,
    bright_font: bool = False,
    bright_bg: bool = False,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    reset: bool = False,
) -> str:
    colors = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

    if reset:
        return "\x1b[0m"

    text = "\x1b["

    if font_color in colors:
        text += f"{90 + colors.index(font_color) if bright_font else 30 + colors.index(font_color)};"

    if bg_color in colors:
        text += f"{100 + colors.index(bg_color) if bright_bg else 40 + colors.index(bg_color)};"

    if bold:
        text += "1;"
    if italic:
        text += "3;"
    if underline:
        text += "4;"
    if strikethrough:
        text += "9;"

    return text.rstrip(";") + "m"


class SimpleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info and not record.exc_text:
            record.exc_text = "\n" + self.formatException(record.exc_info)
        return super().format(record)


class ColoredFormatter(logging.Formatter):
    level_colors = {
        logging.DEBUG: color_code_gen(bg_color="black", bold=True),
        logging.INFO: color_code_gen(font_color="blue", bold=True),
        logging.WARNING: color_code_gen(font_color="yellow", bold=True),
        logging.ERROR: color_code_gen(font_color="red"),
        logging.CRITICAL: color_code_gen(font_color="white", bg_color="red"),
    }
    base_format = (
        color_code_gen(font_color="black")
        + "%(asctime)-22s"
        + color_code_gen(reset=True)
        + color_code_gen(font_color="magenta")
        + "[%(name)s]"
        + color_code_gen(reset=True)
        + " "
        + color_code_gen(font_color="green")
        + "[%(filename)s:%(lineno)d]"
        + color_code_gen(reset=True)
        + "\n{level_color}%(levelname)-21s"
        + color_code_gen(reset=True)
        + " %(message)s\n"
    )

    def __init__(self) -> None:
        super().__init__(datefmt="[%Y-%m-%d %H:%M:%S]")
        self._formatters = {
            level: logging.Formatter(self.base_format.format(level_color=color), self.datefmt)
            for level, color in self.level_colors.items()
        }

    def format(self, record: logging.LogRecord) -> str:
        formatter = self._formatters.get(record.levelno, self._formatters[logging.DEBUG])
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = color_code_gen(font_color="red") + "\n" + text + color_code_gen(reset=True)
        output = formatter.format(record)
        record.exc_text = None
        return output


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

    console_handler.setFormatter(ColoredFormatter() if supports_color(console_handler.stream) else formatter)
    debug_handler.setFormatter(formatter)
    warning_handler.setFormatter(formatter)

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

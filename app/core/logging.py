import logging
from typing import Literal

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
):
    """ANSIカラーコードを生成します。"""

    COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

    if reset:
        return "\x1b[0m"

    text = "\x1b["

    if font_color in COLORS:
        if bright_font:
            text += f"{90 + COLORS.index(font_color)};"
        else:
            text += f"{30 + COLORS.index(font_color)};"

    if bg_color in COLORS:
        if bright_bg:
            text += f"{100 + COLORS.index(bg_color)};"
        else:
            text += f"{40 + COLORS.index(bg_color)};"

    if bold:
        text += "1;"
    if italic:
        text += "3;"
    if underline:
        text += "4;"
    if strikethrough:
        text += "9;"

    text = text.rstrip(";")
    text += "m"

    return text


class NormalFormatter(logging.Formatter):
    """ちょっとだけ改変するためにロギングモジュールをそのままパクりました。"""

    def format(self, record):
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        s = self.formatMessage(record)
        if record.exc_info:
            if not record.exc_text:
                # トレースバック前に改行を追加
                record.exc_text = "\n" + self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
        return s


class ColoredFormatter(logging.Formatter):
    """Discord.pyのものを改変しました。"""

    LEVEL_COLORS = [
        (logging.DEBUG, color_code_gen(bg_color="black", bold=True)),
        (logging.INFO, color_code_gen(font_color="blue", bold=True)),
        (logging.WARNING, color_code_gen(font_color="yellow", bold=True)),
        (logging.ERROR, color_code_gen(font_color="red")),
        (logging.CRITICAL, color_code_gen(font_color="white", bg_color="red")),
    ]

    FORMATS = {
        level: logging.Formatter(
            # 以下、色の設定
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
            + "\n"
            + color
            + "%(levelname)-21s"
            + color_code_gen(reset=True)
            + " "
            + "%(message)s"
            + "\n",
            # 以下、日付（asctime）のフォーマット
            "[%Y-%m-%d %H:%M:%S]",
        )
        for level, color in LEVEL_COLORS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno, self.FORMATS[logging.DEBUG])

        # トレースバックを常に赤色で表示するために上書き
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = color_code_gen(font_color="red") + "\n" + text + color_code_gen(reset=True)

        output = formatter.format(record)

        # キャッシュレイヤーを削除
        record.exc_text = None
        return output


def setup_logger(config: AsteroidConfig):
    """ロガーを設定します。"""

    import os
    from logging import StreamHandler, getLogger
    from logging.handlers import TimedRotatingFileHandler

    from discord.utils import stream_supports_colour as supports_color

    # ログファイルを保存するディレクトリを作成
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # ログのフォーマットを定義
    log_format = "%(asctime)-22s[%(name)s] [%(filename)s:%(lineno)d]\n%(levelname)-21s %(message)s\n"
    log_date_format = "[%Y-%m-%d %H:%M:%S]"
    formatter = NormalFormatter(log_format, log_date_format)

    # ハンドラーを作成
    console_handler = StreamHandler()
    debug_file_handler = TimedRotatingFileHandler(
        filename="logs/debug", when="midnight", backupCount=config.DEBUG_LOG_RETENTION_DAYS
    )
    warning_file_handler = TimedRotatingFileHandler(
        filename="logs/warning", when="midnight", backupCount=config.WARNING_LOG_RETENTION_DAYS
    )

    # ログファイルの名前に日付を追加
    debug_file_handler.suffix = "_%Y-%m-%d.log"
    warning_file_handler.suffix = "_%Y-%m-%d.log"

    # コンソールハンドラーにカラー付きのフォーマッターを設定
    if supports_color(console_handler.stream):
        console_handler.setFormatter(ColoredFormatter())
    else:
        console_handler.setFormatter(formatter)

    # ファイルハンドラーには通常のフォーマッターを設定
    debug_file_handler.setFormatter(formatter)
    warning_file_handler.setFormatter(formatter)

    # ログレベルを設定
    console_handler.setLevel(logging.DEBUG)
    debug_file_handler.setLevel(logging.DEBUG)
    warning_file_handler.setLevel(logging.WARNING)

    # ルートロガーにハンドラーを追加
    root = getLogger()
    root.setLevel(logging.WARNING)
    root.addHandler(console_handler)
    root.addHandler(debug_file_handler)
    root.addHandler(warning_file_handler)

    # 自アプリだけDEBUGレベルでログを出すようにする
    getLogger("asteroid").setLevel(logging.DEBUG)

    getLogger("asteroid.logger").info("ロガーが初期化されました。")

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Sequence
from logging import getLogger
from typing import Any

import discord

from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable

logger = getLogger(__name__)

TRACEBACK_TAIL_LINES = 12
TRACEBACK_MAX_LENGTH = 1800
ErrorReportField = tuple[str, str]


def build_traceback_tail(exception: BaseException) -> str:
    lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
    tail = "".join(lines[-TRACEBACK_TAIL_LINES:]).strip()
    if len(tail) > TRACEBACK_MAX_LENGTH:
        tail = "...\n" + tail[-TRACEBACK_MAX_LENGTH:]
    return tail


def build_traceback_embed(traceback_tail: str) -> discord.Embed:
    return discord.Embed(
        title="トレースバック",
        description=f"```python\n{traceback_tail}\n```",
        color=AsteroidColor.DARK_EMBED_COLOR,
    )


def build_exception_report_embed(
    title: str,
    exception: BaseException,
    fields: Sequence[ErrorReportField] = (),
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=f"`{type(exception).__name__}`: {exception}",
        color=AsteroidColor.WARNING,
    )
    for name, value in fields:
        embed.add_field(name=name, value=value, inline=False)
    return embed


def get_main_log_channel_id(bot: object) -> int:
    config = getattr(bot, "config", None)
    log_config = getattr(config, "log", None)
    channel_id = getattr(log_config, "main_log_channel_id", 0)
    return channel_id if isinstance(channel_id, int) else 0


async def send_exception_report(
    bot: Any,
    *,
    title: str,
    exception: BaseException,
    fields: Sequence[ErrorReportField] = (),
) -> None:
    channel_id = get_main_log_channel_id(bot)
    if not channel_id:
        return

    log_channel = as_messageable(bot.get_channel(channel_id))
    if log_channel is None or not bot.is_operating_channel(log_channel):
        return

    traceback_tail = build_traceback_tail(exception)
    try:
        await log_channel.send(
            embeds=[
                build_exception_report_embed(title, exception, fields),
                build_traceback_embed(traceback_tail),
            ]
        )
    except discord.HTTPException as error:
        logger.warning(
            f"エラー通知の送信に失敗しました: channel_id={channel_id} status={error.status} code={error.code}"
        )
    except Exception:
        logger.warning(f"エラー通知の送信に失敗しました: channel_id={channel_id}", exc_info=True)


async def report_background_task_error(
    bot: Any,
    loop_name: str,
    exception: BaseException,
) -> None:
    if isinstance(exception, asyncio.CancelledError):
        return

    logger.exception(
        f"バックグラウンドタスクで予期しないエラーが発生しました: loop={loop_name}",
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    await send_exception_report(
        bot,
        title="バックグラウンドタスクエラー",
        exception=exception,
        fields=(("タスク", f"`{loop_name}`"),),
    )

import asyncio
import signal
import tracemalloc
from logging import getLogger

from app.core.bot import AsteroidBot
from app.core.config import get_config
from app.core.logging import setup_logger

logger = getLogger("app.launch_app")


def request_signal_shutdown(bot: AsteroidBot, received_signal: signal.Signals) -> None:
    if bot.schedule_graceful_shutdown(f"signal={received_signal.name}"):
        logger.info(f"停止シグナルを受信しました: signal={received_signal.name}")
        return

    logger.warning(f"停止シグナルを受信しましたが、既に停止処理中です: signal={received_signal.name}")


async def run_bot(bot: AsteroidBot, token: str) -> None:
    loop = asyncio.get_running_loop()
    registered_signals: list[signal.Signals] = []

    for shutdown_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(shutdown_signal, request_signal_shutdown, bot, shutdown_signal)
        except NotImplementedError:
            signal.signal(
                shutdown_signal,
                lambda signum, _: loop.call_soon_threadsafe(
                    request_signal_shutdown,
                    bot,
                    signal.Signals(signum),
                ),
            )
        else:
            registered_signals.append(shutdown_signal)

    try:
        async with bot:
            logger.info("BOT を起動します。")
            await bot.start(token)
    finally:
        for shutdown_signal in registered_signals:
            loop.remove_signal_handler(shutdown_signal)
        if bot.shutdown_task is not None:
            await bot.shutdown_task


def main() -> None:
    tracemalloc.start()
    logger.info("アプリケーション起動を開始します。")
    config = get_config()
    setup_logger(config)
    logger.info(
        f"設定を読み込みました: guild_id={config.discord.guild_id} "
        f"sync_commands_on_startup={config.discord.sync_commands_on_startup}"
    )
    logger.info(f"ロガーを初期化しました: level={config.logging.level.upper()}")

    bot = AsteroidBot(config)
    asyncio.run(run_bot(bot, config.discord.token))
    logger.info("BOTを終了します。")


if __name__ == "__main__":
    main()

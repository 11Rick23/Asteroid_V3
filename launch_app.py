import tracemalloc
from logging import getLogger

from app.core.bot import AsteroidBot
from app.core.config import get_config
from app.core.logging import setup_logger

logger = getLogger("app.launch_app")


def main() -> None:
    tracemalloc.start()
    logger.info("アプリケーション起動を開始します。")
    config = get_config()
    setup_logger(config)
    logger.info(
        f"設定を読み込みました: guild_count={len(config.discord.guild_ids)} "
        f"sync_commands_on_startup={config.discord.sync_commands_on_startup}"
    )
    logger.info(f"ロガーを初期化しました: level={config.logging.level.upper()}")

    bot = AsteroidBot(config)
    logger.info("BOT を起動します。")
    bot.run(config.discord.token, log_handler=None)
    logger.info("BOTを終了します。")


if __name__ == "__main__":
    main()

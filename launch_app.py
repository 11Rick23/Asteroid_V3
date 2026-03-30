import tracemalloc
from logging import getLogger

from app.core.bot import AsteroidBot
from app.core.config import get_config
from app.core.logging import setup_logger

logger = getLogger("app.launch_app")


def main() -> None:
    tracemalloc.start()

    config = get_config()
    setup_logger(config)

    bot = AsteroidBot(config)
    bot.run(config.discord.token, log_handler=None)

    logger.info("BOTを終了します。")


if __name__ == "__main__":
    main()

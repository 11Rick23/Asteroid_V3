import tracemalloc
from logging import getLogger

from app.core.bot import AsteroidBot
from app.core.config import get_config
from app.core.logging import setup_logger

logger = getLogger(__name__)


def main():
    tracemalloc.start()

    config = get_config()

    setup_logger(config)

    bot = AsteroidBot(config)

    # どうやらDiscord.pyは優秀なので、ctrl+cでキャンセルするとそれを検知してくれるらしい
    # つまり、bot.run()の後に書いたコードがちゃんとbotを終了した後に実行される
    bot.run(config.DISCORD_BOT_TOKEN, log_handler=None)

    logger.info("BOTを終了します。")


if __name__ == "__main__":
    main()

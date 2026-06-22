from __future__ import annotations

from logging import getLogger

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import AsteroidConfig

logger = getLogger(__name__)


def _normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)

    if url.drivername == "mysql":
        logger.info(f"データベースURLのドライバを補正します: backend={url.get_backend_name()} driver=aiomysql")
        return url.set(drivername="mysql+aiomysql").render_as_string(hide_password=False)

    if url.get_backend_name() == "mysql" and url.get_driver_name() != "aiomysql":
        raise RuntimeError(
            "MySQL 接続には async ドライバが必要です。 database.url を 'mysql+aiomysql://...' に設定してください。"
        )

    return database_url


def create_engine(config: AsteroidConfig) -> AsyncEngine:
    database_url = config.database.url.strip()
    if not database_url:
        raise RuntimeError("database.url が空です。config.yaml に SQLAlchemy 用の接続 URL を設定してください。")
    database_url = _normalize_database_url(database_url)
    url = make_url(database_url)
    logger.info(
        f"DB engine を作成します: backend={url.get_backend_name()} "
        f"driver={url.get_driver_name()} echo={config.database.echo}"
    )

    engine = create_async_engine(
        database_url,
        echo=config.database.echo,
        future=True,
        pool_pre_ping=True,
    )
    logger.info(f"DB engine を作成しました: backend={url.get_backend_name()} driver={url.get_driver_name()}")
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    logger.info("DB session factory を作成しました。")
    return async_sessionmaker(engine, expire_on_commit=False)

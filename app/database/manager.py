from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import AsteroidConfig
from app.database.compat import CompatPool
from app.database.repositories import DatabaseRepositories


class DatabaseManager(DatabaseRepositories):
    def __init__(self, config: AsteroidConfig, engine: AsyncEngine, session_factory: async_sessionmaker):
        super().__init__()
        self.config = config
        self.engine = engine
        self.session = session_factory
        self.pool = CompatPool(engine)
        self.initialized = False

    def is_initialized(self) -> bool:
        return self.initialized

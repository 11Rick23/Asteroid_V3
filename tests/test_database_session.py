from __future__ import annotations

import logging

from app.core.config import AsteroidConfig
from app.database import session as session_module


def test_create_engine_logs_backend_and_driver(monkeypatch, caplog) -> None:
    created: dict[str, object] = {}

    def fake_create_async_engine(database_url: str, **kwargs):
        created["database_url"] = database_url
        created["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(session_module, "create_async_engine", fake_create_async_engine)
    config = AsteroidConfig.model_validate(
        {
            "database": {
                "url": "mysql://user:password@localhost/test_db",
                "echo": True,
            }
        }
    )

    with caplog.at_level(logging.INFO, logger="app.database.session"):
        engine = session_module.create_engine(config)

    assert engine is not None
    assert str(created["database_url"]).startswith("mysql+aiomysql://user:")
    assert "DB engine を作成します: backend=mysql driver=aiomysql echo=True" in caplog.text


def test_create_engine_strips_unsupported_mysql_query_params(monkeypatch, caplog) -> None:
    created: dict[str, object] = {}

    def fake_create_async_engine(database_url: str, **kwargs):
        created["database_url"] = database_url
        created["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(session_module, "create_async_engine", fake_create_async_engine)
    config = AsteroidConfig.model_validate(
        {
            "database": {
                "url": "mysql://user:password@localhost/test_db?advancedSafeModeLevel=SAFE&charset=utf8mb4",
                "echo": False,
            }
        }
    )

    with caplog.at_level(logging.WARNING, logger="app.database.session"):
        session_module.create_engine(config)

    assert "advancedSafeModeLevel" not in str(created["database_url"])
    assert "charset=utf8mb4" in str(created["database_url"])
    assert "MySQL 接続で未対応の URL クエリを除外します: advancedSafeModeLevel" in caplog.text

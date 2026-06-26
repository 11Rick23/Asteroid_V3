from __future__ import annotations

import logging
from typing import Any

from app.core.config import AsteroidConfig
from app.database import session as session_module


def test_create_engine_logs_backend_and_driver(monkeypatch, caplog) -> None:
    """MySQL URL は async driver へ正規化し、使用 backend と driver をログへ残す。"""
    # 機能要件：mysql:// URL を mysql+aiomysql:// に正規化して engine を作成する。
    # 非機能要件：DB 接続 backend と driver を起動時ログで確認できる。
    # Given
    created: dict[str, object] = {}

    def fake_create_async_engine(database_url: str, **kwargs: Any) -> object:
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

    # When
    with caplog.at_level(logging.INFO, logger="app.database.session"):
        engine = session_module.create_engine(config)

    # Then
    assert engine is not None
    assert created["database_url"] == "mysql+aiomysql://user:password@localhost/test_db"
    assert "DB engine を作成します: backend=mysql driver=aiomysql echo=True" in caplog.text

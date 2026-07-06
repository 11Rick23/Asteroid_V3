from __future__ import annotations

from logging import getLogger

from app.database.alembic_logging import configure_alembic_logging


def test_configure_alembic_logging_keeps_existing_app_loggers_enabled():
    """Alembic の logging 設定後も既存の app logger は無効化されない。"""
    # 非機能要件：起動時 migration で Alembic logging を読み込んでもアプリログを無効化しない。
    # Given
    root_logger = getLogger()
    app_logger = getLogger("app.launch_app")
    package_logger = getLogger("app")
    original_root_handlers = list(root_logger.handlers)
    original_root_level = root_logger.level
    original_app_disabled = app_logger.disabled
    original_package_disabled = package_logger.disabled
    app_logger.disabled = False
    package_logger.disabled = False

    try:
        # When
        configure_alembic_logging("alembic.ini")

        # Then
        assert app_logger.disabled is False
        assert package_logger.disabled is False
    finally:
        root_logger.handlers[:] = original_root_handlers
        root_logger.setLevel(original_root_level)
        app_logger.disabled = original_app_disabled
        package_logger.disabled = original_package_disabled

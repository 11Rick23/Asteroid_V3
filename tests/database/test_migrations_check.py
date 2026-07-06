from __future__ import annotations

import pytest

from app.database import migrations_check
from app.database.migrations_check import validate_database_revision


def test_upgrade_database_to_head_runs_alembic_upgrade(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """DB migration 自動適用では Alembic の head まで upgrade する。"""
    # 機能要件：起動前 migration は Alembic revision を head まで適用する。
    # Given
    config_path = tmp_path / "alembic.ini"
    config_path.write_text("[alembic]\nscript_location = app/database/migrations\n", encoding="utf-8")
    calls: list[tuple[str | None, str]] = []

    def fake_upgrade(config, revision: str) -> None:
        calls.append((config.config_file_name, revision))

    monkeypatch.setattr(migrations_check.command, "upgrade", fake_upgrade)

    # When
    migrations_check.upgrade_database_to_head(config_path)

    # Then
    assert calls == [(str(config_path), "head")]


def test_accepts_current_heads():
    """DB revision と migration head が一致する場合は成功する。"""
    # 機能要件：DB revision が migration head と一致する場合は起動前チェックを通す。
    # Given
    current_heads = ("head-a", "head-b")
    expected_heads = ("head-b", "head-a")

    # When / Then
    validate_database_revision(current_heads, expected_heads)


def test_rejects_missing_expected():
    """migration head が取得できない場合は構成不備として失敗する。"""
    # 非機能要件：migration head が取得できない構成不備では起動前チェックを失敗させる。
    # Given
    current_heads = ("head-a",)
    expected_heads: tuple[str, ...] = ()

    # When / Then
    with pytest.raises(RuntimeError, match="migration head が見つかりません"):
        validate_database_revision(current_heads, expected_heads)


def test_rejects_unstamped_database():
    """DB に Alembic revision が記録されていない場合は stamp 手順を案内する。"""
    # 非機能要件：Alembic 管理外の DB では誤起動せず stamp 手順を案内する。
    # Given
    current_heads: tuple[str, ...] = ()
    expected_heads = ("head-a",)

    # When / Then
    with pytest.raises(RuntimeError, match="stamp"):
        validate_database_revision(current_heads, expected_heads)


def test_rejects_old_database():
    """DB revision が migration head と異なる場合は upgrade 手順を案内する。"""
    # 非機能要件：古い DB schema では誤起動せず upgrade 手順を案内する。
    # Given
    current_heads = ("old-head",)
    expected_heads = ("new-head",)

    # When / Then
    with pytest.raises(RuntimeError, match="upgrade head"):
        validate_database_revision(current_heads, expected_heads)

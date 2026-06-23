from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy.engine import URL, make_url

from scripts import v2_to_v3_migration as migration
from scripts.v2_to_v3_migration import build_mysql_database_url


def test_build_mysql_database_url_encodes_reserved_characters() -> None:
    url = build_mysql_database_url(
        user="root",
        password="pa@ss:wo/rd#100%",
        host="127.0.0.1",
        port=3306,
        database="asteroid-v2",
    )

    assert url == "mysql://root:pa%40ss%3Awo%2Frd%23100%25@127.0.0.1:3306/asteroid-v2"


def test_migration_table_names_are_pinned_to_init_baseline() -> None:
    table_names = migration.get_migration_table_names()

    assert table_names == [
        table_name
        for table_name in migration.BASELINE_TABLE_NAMES
        if table_name not in migration.TARGET_ONLY_TABLES
    ]
    assert "monthly_action_powers" not in table_names
    assert "leveling_hotness_events" not in table_names


def test_target_database_must_not_have_existing_tables() -> None:
    with pytest.raises(RuntimeError, match="空のDB"):
        migration.ensure_target_database_is_empty({migration.ALEMBIC_VERSION_TABLE})

    with pytest.raises(RuntimeError, match="空のDB"):
        migration.ensure_target_database_is_empty({"given_stars"})


def test_run_alembic_upgrade_uses_target_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, str], str]] = []

    def fake_run_command(
        command: list[str], *, env: dict[str, str], label: str, stdin: object = None
    ) -> subprocess.CompletedProcess[str]:
        del stdin
        calls.append((command, env, label))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(migration, "run_command", fake_run_command)

    target_url = make_url("mysql://user:secret@127.0.0.1:3306/asteroid_v3")
    migration.run_alembic_upgrade(target_url, migration.BASELINE_REVISION)

    assert calls == [
        (
            ["uv", "run", "alembic", "upgrade", migration.BASELINE_REVISION],
            calls[0][1],
            f"Alembic upgrade ({migration.BASELINE_REVISION})",
        )
    ]
    assert calls[0][1]["ASTEROID_DATABASE_URL"] == "mysql://user:secret@127.0.0.1:3306/asteroid_v3"
    assert "secret" not in " ".join(calls[0][0])


def test_migrate_applies_baseline_imports_data_then_upgrades_head(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, object]] = []

    def fake_run_alembic_upgrade(target_url: URL, revision: str) -> None:
        assert target_url.database == "asteroid_v3"
        events.append(("upgrade", revision))

    def fake_dump_source_data(source_url: URL, dump_path: Path, tables: list[str]) -> None:
        assert source_url.database == "asteroid_v2"
        assert tables == migration.get_migration_table_names()
        events.append(("dump", tuple(tables)))

    def fake_import_dump(target_url: URL, dump_path: Path) -> None:
        assert target_url.database == "asteroid_v3"
        events.append(("import", dump_path.suffix))

    monkeypatch.setattr(migration, "verify_mysql_cli", lambda: None)
    monkeypatch.setattr(
        migration,
        "get_source_table_names",
        lambda source_url: set(migration.get_migration_table_names()),
    )
    monkeypatch.setattr(migration, "get_target_table_names", lambda target_url: set())
    monkeypatch.setattr(migration, "run_alembic_upgrade", fake_run_alembic_upgrade)
    monkeypatch.setattr(migration, "dump_source_data", fake_dump_source_data)
    monkeypatch.setattr(migration, "import_dump", fake_import_dump)

    migration.migrate(
        source_database_url="mysql://user:secret@127.0.0.1:3306/asteroid_v2",
        target_database_url="mysql://user:secret@127.0.0.1:3306/asteroid_v3",
        batch_size=1000,
        echo=False,
    )

    assert events == [
        ("upgrade", migration.BASELINE_REVISION),
        ("dump", tuple(migration.get_migration_table_names())),
        ("import", ".sql"),
        ("upgrade", migration.HEAD_REVISION),
    ]

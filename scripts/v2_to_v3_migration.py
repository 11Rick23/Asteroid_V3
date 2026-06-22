from __future__ import annotations

import argparse
import getpass
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

from sqlalchemy.engine import URL, make_url

logger = logging.getLogger(__name__)

BASELINE_REVISION = "273b6467e5ff"
HEAD_REVISION = "head"
ALEMBIC_DATABASE_URL_ENV = "ASTEROID_DATABASE_URL"
ALEMBIC_VERSION_TABLE = "alembic_version"
BASELINE_TABLE_NAMES = (
    "given_stars",
    "monthly_action_powers",
    "monthly_powers",
    "role_panel_categories",
    "star_grades",
    "starred_messages",
    "user_birthdays",
    "user_roles",
    "voice_xp_limits",
    "xp_boosts",
    "role_panel_roles",
)
TARGET_ONLY_TABLES = frozenset({"monthly_action_powers"})
MIGRATION_TABLE_NAMES = tuple(
    table_name for table_name in BASELINE_TABLE_NAMES if table_name not in TARGET_ONLY_TABLES
)
UNSUPPORTED_MYSQL_QUERY_KEYS = {"advancedSafeModeLevel"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asteroid V2 DB から V3 DB へデータを移行します。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source-database-url",
        dest="source_database_url",
        help="移行元DBの接続URL。未指定なら実行時に入力します",
    )
    parser.add_argument(
        "--target-database-url",
        dest="target_database_url",
        help="移行先DBの接続URL。未指定なら実行時に入力します",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="CLI ベース移行では未使用です。互換性のため残しています",
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        help="詳細ログを有効化します",
    )
    return parser.parse_args()


def prompt_database_url(label: str, provided_value: str | None) -> str:
    if provided_value is not None and provided_value.strip():
        return provided_value.strip()

    value = input(f"{label} DB URL (空欄なら個別入力): ").strip()
    if value:
        return value
    return prompt_database_components(label)


def prompt_with_default(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def build_mysql_database_url(user: str, password: str, host: str, port: int, database: str) -> str:
    return f"mysql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(database, safe='')}"


def prompt_database_components(label: str) -> str:
    print(f"{label} DB 接続情報を入力してください。")
    host = prompt_with_default(f"{label} host", "127.0.0.1")
    port_text = prompt_with_default(f"{label} port", "3306")
    user = input(f"{label} user: ").strip()
    password = getpass.getpass(f"{label} password: ")
    database = input(f"{label} database: ").strip()

    if not user:
        raise RuntimeError(f"{label} user が空です。")
    if not database:
        raise RuntimeError(f"{label} database が空です。")

    try:
        port = int(port_text)
    except ValueError as error:
        raise RuntimeError(f"{label} port は整数で指定してください。") from error

    return build_mysql_database_url(user, password, host, port, database)


def normalize_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    unsupported_query_keys = sorted(UNSUPPORTED_MYSQL_QUERY_KEYS & set(url.query))
    if url.get_backend_name() != "mysql":
        raise RuntimeError("MySQL 接続 URL を指定してください。")
    if unsupported_query_keys:
        logger.warning("MySQL 接続で未対応の URL クエリを除外します: %s", ", ".join(unsupported_query_keys))
        url = url.difference_update_query(unsupported_query_keys)
    return url


def _masked_url(url: URL) -> str:
    return url.render_as_string(hide_password=True)


def _connection_env(url: URL) -> dict[str, str]:
    env = dict(os.environ)
    env["MYSQL_PWD"] = url.password or ""
    return env


def _mysql_connection_args(url: URL) -> list[str]:
    if not url.username:
        raise RuntimeError("DB URL に user が含まれていません。")
    if not url.database:
        raise RuntimeError("DB URL に database が含まれていません。")
    return [
        "--protocol=TCP",
        f"--host={url.host or '127.0.0.1'}",
        f"--port={url.port or 3306}",
        f"--user={url.username}",
    ]


def run_command(
    command: list[str], *, env: dict[str, str], label: str, stdin=None
) -> subprocess.CompletedProcess[str]:
    logger.debug("Running command: %s", " ".join(command))
    try:
        return subprocess.run(
            command,
            env=env,
            stdin=stdin,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"{label} に失敗しました: {stderr}") from error


def run_mysql_query(url: URL, query: str, *, label: str) -> list[str]:
    command = ["mysql", *_mysql_connection_args(url), f"--database={url.database}"]
    command.extend(["--batch", "--skip-column-names", f"--execute={query}"])
    result = run_command(command, env=_connection_env(url), label=label)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def dump_source_data(source_url: URL, dump_path: Path, tables: list[str]) -> None:
    if source_url.database is None:
        raise ValueError("移行元DB名が指定されていません。")
    command = ["mysqldump", *_mysql_connection_args(source_url)]
    command.extend(
        [
            "--single-transaction",
            "--skip-lock-tables",
            "--skip-comments",
            "--no-create-info",
            "--skip-triggers",
            source_url.database,
            *tables,
        ]
    )
    logger.info("移行元DBをダンプします: source=%s", _masked_url(source_url))
    with dump_path.open("w", encoding="utf-8") as dump_file:
        try:
            subprocess.run(
                command,
                env=_connection_env(source_url),
                stdout=dump_file,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").strip()
            raise RuntimeError(f"source DB のダンプに失敗しました: {stderr}") from error


def import_dump(target_url: URL, dump_path: Path) -> None:
    command = ["mysql", *_mysql_connection_args(target_url), f"--database={target_url.database}"]
    logger.info("ダンプを移行先DBへ投入します: target=%s", _masked_url(target_url))
    with dump_path.open("r", encoding="utf-8") as dump_file:
        try:
            subprocess.run(
                command,
                env=_connection_env(target_url),
                stdin=dump_file,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").strip()
            raise RuntimeError(f"target DB へのインポートに失敗しました: {stderr}") from error


def get_source_table_names(source_url: URL) -> set[str]:
    lines = run_mysql_query(source_url, "SHOW TABLES", label="source DB のテーブル一覧取得")
    return set(lines)


def get_target_table_names(target_url: URL) -> set[str]:
    lines = run_mysql_query(target_url, "SHOW TABLES", label="target DB のテーブル一覧取得")
    return set(lines)


def ensure_target_database_is_empty(table_names: set[str]) -> None:
    if table_names:
        existing_tables = ", ".join(sorted(table_names))
        raise RuntimeError(f"移行先DBに既存テーブルがあります。空のDBを指定してください: {existing_tables}")


def get_migration_table_names() -> list[str]:
    return list(MIGRATION_TABLE_NAMES)


def verify_mysql_cli() -> None:
    for executable in ("mysql", "mysqldump", "uv"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"`{executable}` コマンドが見つかりません。必要な CLI をインストールしてください。")


def run_alembic_upgrade(target_url: URL, revision: str) -> None:
    env = dict(os.environ)
    env[ALEMBIC_DATABASE_URL_ENV] = target_url.render_as_string(hide_password=False)
    run_command(["uv", "run", "alembic", "upgrade", revision], env=env, label=f"Alembic upgrade ({revision})")


def migrate(source_database_url: str, target_database_url: str, batch_size: int, echo: bool) -> None:
    del batch_size, echo

    verify_mysql_cli()
    source_url = normalize_database_url(source_database_url)
    target_url = normalize_database_url(target_database_url)

    migration_table_names = get_migration_table_names()
    expected_source_tables = set(migration_table_names)

    logger.info("移行元DBへ接続します: %s", _masked_url(source_url))
    source_table_names = get_source_table_names(source_url)
    missing_source_tables = sorted(expected_source_tables - source_table_names)
    if missing_source_tables:
        raise RuntimeError("移行元DBに必要なテーブルが不足しています: " + ", ".join(missing_source_tables))

    extra_source_tables = sorted(source_table_names - expected_source_tables)
    if extra_source_tables:
        logger.warning("移行対象外のテーブルを検出しました: %s", ", ".join(extra_source_tables))

    logger.info("移行先DBへ接続します: %s", _masked_url(target_url))
    existing_target_tables = get_target_table_names(target_url)
    ensure_target_database_is_empty(existing_target_tables)
    run_alembic_upgrade(target_url, BASELINE_REVISION)

    with tempfile.NamedTemporaryFile(prefix="asteroid_v2_to_v3_", suffix=".sql", delete=True) as dump_file:
        dump_path = Path(dump_file.name)
        dump_source_data(source_url, dump_path, migration_table_names)
        import_dump(target_url, dump_path)

    run_alembic_upgrade(target_url, HEAD_REVISION)

    logger.info(
        "Migration completed: copied_tables=%s baseline_revision=%s final_revision=%s",
        len(migration_table_names),
        BASELINE_REVISION,
        HEAD_REVISION,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        args = parse_args()
        source_database_url = prompt_database_url("source", args.source_database_url)
        target_database_url = prompt_database_url("target", args.target_database_url)
        migrate(
            source_database_url=source_database_url,
            target_database_url=target_database_url,
            batch_size=args.batch_size,
            echo=args.echo,
        )
    except RuntimeError as error:
        logger.error(str(error))
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()

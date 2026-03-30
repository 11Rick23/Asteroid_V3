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

from sqlalchemy.dialects import mysql
from sqlalchemy.engine import URL, make_url
from sqlalchemy.schema import CreateTable

import app.database.models  # noqa: F401
from app.database.base import Base

logger = logging.getLogger(__name__)

TARGET_ONLY_TABLES = {"monthly_action_powers"}
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


def run_mysql_script_with_input(url: URL, sql: str, *, label: str) -> None:
    command = ["mysql", *_mysql_connection_args(url), f"--database={url.database}"]
    try:
        subprocess.run(
            command,
            env=_connection_env(url),
            input=sql,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"{label} に失敗しました: {stderr}") from error


def dump_source_data(source_url: URL, dump_path: Path, tables: list[str]) -> None:
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


def ensure_target_tables_are_empty(target_url: URL, table_names: set[str]) -> None:
    non_empty_tables: list[str] = []
    for table_name in sorted(table_names):
        count_result = run_mysql_query(
            target_url,
            f"SELECT COUNT(*) FROM `{table_name}`",
            label=f"target DB のテーブル件数確認 ({table_name})",
        )
        row_count = int(count_result[0]) if count_result else 0
        if row_count > 0:
            non_empty_tables.append(f"{table_name} ({row_count} rows)")
    if non_empty_tables:
        raise RuntimeError("移行先DBに既存データがあります。空のDBを指定してください: " + ", ".join(non_empty_tables))


def create_target_tables(target_url: URL) -> None:
    dialect = mysql.dialect()
    statements = [
        str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)) for table in Base.metadata.sorted_tables
    ]
    run_mysql_script_with_input(
        target_url,
        ";\n".join(statements) + ";\n",
        label="target DB のテーブル作成",
    )


def get_migration_table_names() -> list[str]:
    return [table.name for table in Base.metadata.sorted_tables if table.name not in TARGET_ONLY_TABLES]


def verify_mysql_cli() -> None:
    for executable in ("mysql", "mysqldump"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"`{executable}` コマンドが見つかりません。MySQL CLI をインストールしてください。")


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
    relevant_target_tables = existing_target_tables & {table.name for table in Base.metadata.sorted_tables}
    ensure_target_tables_are_empty(target_url, relevant_target_tables)
    create_target_tables(target_url)

    with tempfile.NamedTemporaryFile(prefix="asteroid_v2_to_v3_", suffix=".sql", delete=True) as dump_file:
        dump_path = Path(dump_file.name)
        dump_source_data(source_url, dump_path, migration_table_names)
        import_dump(target_url, dump_path)

    logger.info(
        "Migration completed: copied_tables=%s created_tables=%s",
        len(migration_table_names),
        len(Base.metadata.sorted_tables),
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

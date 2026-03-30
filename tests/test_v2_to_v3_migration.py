from __future__ import annotations

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

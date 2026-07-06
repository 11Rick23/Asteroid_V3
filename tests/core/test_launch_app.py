from __future__ import annotations

from types import SimpleNamespace

import launch_app


def build_config(*, auto_upgrade_on_startup: bool) -> SimpleNamespace:
    return SimpleNamespace(
        database=SimpleNamespace(auto_upgrade_on_startup=auto_upgrade_on_startup),
        discord=SimpleNamespace(
            guild_id=123,
            sync_commands_on_startup=True,
            token="token",
        ),
        logging=SimpleNamespace(level="INFO"),
    )


def test_main_runs_auto_upgrade_before_bot(monkeypatch):
    """自動 migration が有効な場合は Bot 生成前に DB を更新する。"""
    # 機能要件：database.auto_upgrade_on_startup=True では Bot 起動前に migration を適用する。
    # 非機能要件：migration 適用前に Bot を生成せず、古い schema で起動しない。
    # Given
    events: list[str] = []
    config = build_config(auto_upgrade_on_startup=True)

    class FakeBot:
        def __init__(self, _config) -> None:
            events.append("bot")

    def fake_run_bot(_bot, token: str):
        events.append(f"run_bot:{token}")
        return object()

    monkeypatch.setattr(launch_app.tracemalloc, "start", lambda: events.append("tracemalloc"))
    monkeypatch.setattr(launch_app, "get_config", lambda: config)
    monkeypatch.setattr(launch_app, "setup_logger", lambda _config: events.append("setup_logger"))
    monkeypatch.setattr(launch_app, "upgrade_database_to_head", lambda: events.append("upgrade"))
    monkeypatch.setattr(launch_app, "AsteroidBot", FakeBot)
    monkeypatch.setattr(launch_app, "run_bot", fake_run_bot)
    monkeypatch.setattr(launch_app.asyncio, "run", lambda _awaitable: events.append("asyncio.run"))

    # When
    launch_app.main()

    # Then
    assert events == [
        "tracemalloc",
        "setup_logger",
        "upgrade",
        "bot",
        "run_bot:token",
        "asyncio.run",
    ]


def test_main_skips_auto_upgrade_when_disabled(monkeypatch):
    """自動 migration が無効な場合は起動前 upgrade を実行しない。"""
    # 機能要件：database.auto_upgrade_on_startup=False では起動時 migration を実行しない。
    # Given
    events: list[str] = []
    config = build_config(auto_upgrade_on_startup=False)

    class FakeBot:
        def __init__(self, _config) -> None:
            events.append("bot")

    def fake_run_bot(_bot, token: str):
        events.append(f"run_bot:{token}")
        return object()

    monkeypatch.setattr(launch_app.tracemalloc, "start", lambda: events.append("tracemalloc"))
    monkeypatch.setattr(launch_app, "get_config", lambda: config)
    monkeypatch.setattr(launch_app, "setup_logger", lambda _config: events.append("setup_logger"))
    monkeypatch.setattr(launch_app, "upgrade_database_to_head", lambda: events.append("upgrade"))
    monkeypatch.setattr(launch_app, "AsteroidBot", FakeBot)
    monkeypatch.setattr(launch_app, "run_bot", fake_run_bot)
    monkeypatch.setattr(launch_app.asyncio, "run", lambda _awaitable: events.append("asyncio.run"))

    # When
    launch_app.main()

    # Then
    assert events == ["tracemalloc", "setup_logger", "bot", "run_bot:token", "asyncio.run"]

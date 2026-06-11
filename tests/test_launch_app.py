from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from typing import Any

import pytest

from app.common.offline import OfflineInfo
from launch_app import request_signal_shutdown, run_bot


class FakeBot:
    def __init__(self) -> None:
        self.offline_info: list[OfflineInfo] = []
        self.shutdown_requested = False

    def schedule_graceful_shutdown(self, info: OfflineInfo) -> bool:
        if self.shutdown_requested:
            return False

        self.shutdown_requested = True
        self.offline_info.append(info)
        return True


def test_request_signal_shutdown_starts_graceful_shutdown() -> None:
    bot = FakeBot()

    request_signal_shutdown(bot, signal.SIGTERM)  # type: ignore[arg-type]

    assert bot.shutdown_requested is True
    assert bot.offline_info == [
        OfflineInfo(
            reason="SIGTERM シグナルによる強制停止",
            planned_period="未定",
        )
    ]


def test_request_signal_shutdown_ignores_duplicate_signal() -> None:
    bot = FakeBot()
    bot.shutdown_requested = True

    request_signal_shutdown(bot, signal.SIGTERM)  # type: ignore[arg-type]

    assert bot.offline_info == []


class FakeLoop:
    def __init__(self) -> None:
        self.removed_signals: list[signal.Signals] = []

    def add_signal_handler(self, *_: Any) -> None:
        raise NotImplementedError

    def call_soon_threadsafe(self, callback: Callable[..., object], *args: object) -> None:
        callback(*args)

    def remove_signal_handler(self, shutdown_signal: signal.Signals) -> None:
        self.removed_signals.append(shutdown_signal)


class FakeAsyncBot(FakeBot):
    def __init__(self) -> None:
        super().__init__()
        self.shutdown_task = None

    async def __aenter__(self) -> FakeAsyncBot:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def start(self, token: str) -> None:
        return None


@pytest.mark.asyncio
async def test_run_bot_restores_fallback_signal_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = FakeLoop()
    original_handlers: dict[signal.Signals, object] = {
        signal.SIGTERM: object(),
        signal.SIGINT: object(),
    }
    current_handlers = original_handlers.copy()

    def fake_signal(shutdown_signal: signal.Signals, handler: object) -> object:
        previous_handler = current_handlers[shutdown_signal]
        current_handlers[shutdown_signal] = handler
        return previous_handler

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(signal, "getsignal", lambda shutdown_signal: current_handlers[shutdown_signal])
    monkeypatch.setattr(signal, "signal", fake_signal)

    await run_bot(FakeAsyncBot(), "token")  # type: ignore[arg-type]

    assert current_handlers == original_handlers

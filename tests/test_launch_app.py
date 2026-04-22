from __future__ import annotations

import signal

from launch_app import request_signal_shutdown


class FakeBot:
    def __init__(self) -> None:
        self.reasons: list[str] = []
        self.shutdown_requested = False

    def schedule_graceful_shutdown(self, reason: str) -> bool:
        if self.shutdown_requested:
            return False

        self.shutdown_requested = True
        self.reasons.append(reason)
        return True


def test_request_signal_shutdown_starts_graceful_shutdown() -> None:
    bot = FakeBot()

    request_signal_shutdown(bot, signal.SIGTERM)  # type: ignore[arg-type]

    assert bot.shutdown_requested is True
    assert bot.reasons == ["signal=SIGTERM"]


def test_request_signal_shutdown_ignores_duplicate_signal() -> None:
    bot = FakeBot()
    bot.shutdown_requested = True

    request_signal_shutdown(bot, signal.SIGTERM)  # type: ignore[arg-type]

    assert bot.reasons == []

from __future__ import annotations

import logging
from typing import Any, cast

from app.features.punish import service
from tests.support.discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeUser


def test_generates_reason(monkeypatch):
    """処罰理由には実行時刻と moderator 名を含める。"""
    # Given
    guild = FakeGuild()
    moderator = FakeMember(member_id=1, guild=guild, name="moderator")
    monkeypatch.setattr(service, "generate_timestamp", lambda: "2026/06/23 12:00:00")

    # When
    reason = service.generate_reason(cast(Any, moderator))

    # Then
    assert reason == "[2026/06/23 12:00:00] moderator によって処罰が行われました。"


def test_logs_action(caplog):
    """処罰操作ログには action、guild、moderator、target を含める。"""
    # Given
    interaction = FakeInteraction(
        client=object(),
        guild_id=123,
        user=FakeUser(10),
    )
    interaction.guild = type("FakeGuild", (), {"id": 123})()

    # When
    with caplog.at_level(logging.INFO):
        service.log_punishment_action("ban", cast(Any, interaction), target_id=20, probation="なし")

    # Then
    assert "action=ban" in caplog.text
    assert "guild_id=123" in caplog.text
    assert "moderator_id=10" in caplog.text
    assert "target_id=20" in caplog.text

from __future__ import annotations

from app.core.system_commands import stop_bot


def test_stop_metadata():
    """stop command は guild 限定で、公開引数名と説明を日本語で登録する。"""
    # Given / When
    params = stop_bot.parameters
    reason = params[0]
    planned_period = params[1]

    # Then
    assert stop_bot.name == "stop"
    assert stop_bot.description == "BOTを安全に停止します。"
    assert stop_bot.guild_only is True
    assert reason.display_name == "理由"
    assert reason.description == "BOTを停止する理由"
    assert planned_period.display_name == "予定期間"
    assert planned_period.description == "BOTがオフラインとなる予定期間"

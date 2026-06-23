from __future__ import annotations

from discord import app_commands

from app.features.log.error import get_expected_app_command_error_message, unwrap_app_command_error


async def _dummy_callback(_interaction):
    return None


def test_unwraps_invoke_error():
    """CommandInvokeError は内部の original exception を報告対象にする。"""
    # Given
    original = RuntimeError("failed")
    command = app_commands.Command(name="dummy", description="dummy", callback=_dummy_callback)
    exception = app_commands.CommandInvokeError(command, original)

    # When / Then
    assert unwrap_app_command_error(exception) is original


def test_maps_expected_error():
    """想定済み app command error はユーザー向けの定型文に変換する。"""
    # Given
    exception = app_commands.MissingPermissions(["administrator"])

    # When
    message = get_expected_app_command_error_message(exception)

    # Then
    assert message == "権限が足りません！"

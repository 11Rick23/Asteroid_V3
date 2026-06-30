from __future__ import annotations

from app.common.error_reporting import build_exception_report_embed, build_traceback_embed, build_traceback_tail
from app.common.interaction_errors import build_error_embed, format_rate_limited_error


def test_builds_traceback_tail():
    """例外の traceback tail は送信用の短い文字列として生成する。"""
    # 機能要件：例外の種類とメッセージを traceback tail に含める。
    # 非機能要件：Discord 送信に使える長さへ traceback 表示を制限する。
    # Given
    try:
        raise ValueError("broken")
    except ValueError as error:
        exception = error

    # When
    tail = build_traceback_tail(exception)

    # Then
    assert "ValueError: broken" in tail
    assert len(tail) <= 1805


def test_builds_error_embeds():
    """エラー表示用 Embed はユーザー向けメッセージと traceback を分離して作成する。"""
    # 機能要件：ユーザー向けエラーと開発者向け traceback を別 Embed として作成する。
    # Given
    exception = RuntimeError("failed")

    # When
    report_embed = build_exception_report_embed("アプリコマンドエラー", exception, (("コマンド", "`stop`"),))
    traceback_embed = build_traceback_embed("RuntimeError: failed")
    user_embed = build_error_embed("失敗しました。")

    # Then
    assert report_embed.title == "アプリコマンドエラー"
    assert report_embed.description == "`RuntimeError`: failed"
    assert report_embed.fields[0].name == "コマンド"
    assert traceback_embed.title == "トレースバック"
    assert "```python" in (traceback_embed.description or "")
    assert user_embed.title == "エラー"
    assert user_embed.description == "失敗しました。"


def test_formats_rate_limit():
    """rate limit メッセージは秒数を 1 桁に丸めて再試行案内に含める。"""
    # 機能要件：rate limit 発生時は再試行までの秒数をユーザー案内に含める。
    # Given / When
    message = format_rate_limited_error(12.34, action="VC名を変更できませんでした。")

    # Then
    assert message == "Discordのレート制限によりVC名を変更できませんでした。`12.3秒後`に再試行してください。"

from __future__ import annotations

from app.features.starboard.commands import _build_setup_error, _build_setup_summary


def test_builds_setup_summary():
    """スターボード再作成完了メッセージは対象、再作成、欠損削除の件数を含める。"""
    # 機能要件：スターボード再作成完了時は対象、再作成、欠損削除の件数を通知する。
    # Given / When
    message = _build_setup_summary(total_count=10, recreated_count=8, deleted_count=2)

    # Then
    assert "対象件数: 10" in message
    assert "再作成件数: 8" in message
    assert "欠損削除件数: 2" in message


def test_builds_setup_error():
    """スターボード再作成中断メッセージは処理済み件数を含める。"""
    # 機能要件：スターボード再作成中断時は進捗件数を通知する。
    # Given / When
    message = _build_setup_error("中断しました。", 10, 4, 1, 5)

    # Then
    assert message.startswith("中断しました。")
    assert "対象件数: 10" in message
    assert "処理済み件数: 5" in message
    assert "再作成件数: 4" in message
    assert "欠損削除件数: 1" in message

from __future__ import annotations

from datetime import UTC, datetime

from app.common.offline import OfflineInfo, build_offline_embed


def test_builds_from_signal():
    """シグナル停止情報は強制停止理由と未定の予定期間を持つ。"""
    # 機能要件：シグナル停止は停止理由と予定期間を OfflineInfo として表現する。
    # Given / When
    info = OfflineInfo.from_signal("SIGTERM")

    # Then
    assert info.reason == "SIGTERM シグナルによる強制停止"
    assert info.planned_period == "未定"


def test_builds_embed():
    """オフライン Embed は理由、予定期間、緊急連絡先、最終更新日時を表示する。"""
    # 機能要件：オフライン表示には停止理由、予定期間、連絡先、更新日時を含める。
    # Given
    info = OfflineInfo(reason="メンテナンス", planned_period="10分")
    updated_at = datetime(2026, 6, 23, 12, 0, tzinfo=UTC)

    # When
    embed = build_offline_embed(info, "現在停止中です。", ("<@1>", "<@2>"), updated_at=updated_at)

    # Then
    assert embed.title == "BOT は現在オフラインです"
    assert embed.description == "現在停止中です。"
    fields = {field.name: field.value for field in embed.fields}
    assert fields["理由"] == "メンテナンス"
    assert fields["予定期間"] == "10分"
    assert fields["緊急連絡先"] == "<@1>\n<@2>"
    assert fields["最終更新日時"] == "<t:1782216000:F>"

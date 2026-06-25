from __future__ import annotations

from app.features.report.cog import ReportCog


def test_report_metadata():
    """report command は guild 限定で日本語引数を公開する。"""
    # 機能要件：report command は対象ユーザー、違反内容、画像を日本語引数として公開する。
    # 非機能要件：report command は guild 内通報として guild 限定で公開される。
    # Given
    command = ReportCog.report

    # When / Then
    assert command.name == "report"
    assert command.guild_only is True
    assert [parameter.display_name for parameter in command.parameters] == ["対象ユーザー", "違反内容", "画像"]

from __future__ import annotations

from app.common.constants import AsteroidColor
from app.features.moderation.service import build_report_embed, build_resolved_report_embed


class FakeAvatar:
    url = "https://example.com/avatar.png"


class FakeUser:
    display_name = "tester"
    display_avatar = FakeAvatar()


def test_build_report_embed_sets_pending_footer() -> None:
    embed = build_report_embed(FakeUser(), "report body")

    assert embed.description == "report body"
    assert embed.colour.value == AsteroidColor.WARNING
    assert embed.footer.text == "未対応"
    assert embed.author.name == "tester"


def test_build_resolved_report_embed_sets_resolved_state() -> None:
    embed = build_report_embed(FakeUser(), "report body")

    resolved = build_resolved_report_embed(embed, FakeUser())

    assert resolved.colour.value == AsteroidColor.SUCCESS
    assert resolved.footer.text == "tester によって対応済み"

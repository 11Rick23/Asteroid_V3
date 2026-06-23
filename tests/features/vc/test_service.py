from __future__ import annotations

from typing import Any, cast

import discord

from app.features.vc.service import VoiceCreateService, build_select_default_values


class _VCConfig:
    voice_create_channel_id = 10
    voice_category_id = 20


class _Config:
    vc = _VCConfig()


class _Bot:
    config = _Config()
    services: dict[str, object] = {}

    def remember_message(self, _message: object) -> None:
        return None


class _Message:
    id = 55


class _Channel:
    id = 100


def test_builds_default_values():
    """UserSelect の default_values は Discord 上限に合わせて先頭 25 人だけを使う。"""
    # Given
    members = [type("FakeMember", (), {"id": member_id})() for member_id in range(30)]

    # When
    values = build_select_default_values(cast(Any, members))

    # Then
    assert len(values) == 25
    assert [value.id for value in values] == list(range(25))


def test_normalizes_color():
    """VC パネル色は discord.Color、int、未指定を安定した int 値に正規化する。"""
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))

    # When / Then
    assert service.normalize_color(discord.Color(0x123456)) == 0x123456
    assert service.normalize_color(0x654321) == 0x654321
    assert isinstance(service.normalize_color(None), int)


def test_tracks_message():
    """VC コントロールメッセージは channel ID ごとに message ID と色を記録する。"""
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))

    # When
    service.track_control_message(cast(Any, _Channel()), cast(Any, _Message()), color=0x123456)

    # Then
    assert service.control_panel_messages[100] == (55, 0x123456)


def test_untracks_message():
    """追跡解除は channel ID と message ID が一致した場合だけ状態を削除する。"""
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))
    service.control_panel_messages[100] = (55, 0x123456)

    # When
    service.untrack_control_message(100, 999)
    still_tracked = dict(service.control_panel_messages)
    service.untrack_control_message(100, 55)

    # Then
    assert still_tracked == {100: (55, 0x123456)}
    assert service.control_panel_messages == {}

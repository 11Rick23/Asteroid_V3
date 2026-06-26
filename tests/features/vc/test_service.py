from __future__ import annotations

from typing import Any, cast

import discord
import pytest

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


class _VoiceChannel:
    id = 100

    guild = type("FakeGuild", (), {"id": 12345})()


class _Actor:
    id = 200


def test_builds_default_values():
    """UserSelect の default_values は Discord 上限に合わせて先頭 25 人だけを使う。"""
    # 機能要件：VC 権限 UserSelect は現在の許可メンバーを初期選択に反映する。
    # 非機能要件：Discord の default_values 上限に合わせて 25 件までに制限する。
    # Given
    members = [type("FakeMember", (), {"id": member_id})() for member_id in range(30)]

    # When
    values = build_select_default_values(cast(Any, members))

    # Then
    assert len(values) == 25
    assert [value.id for value in values] == list(range(25))


def test_normalizes_color():
    """VC パネル色は discord.Color、int、未指定を安定した int 値に正規化する。"""
    # 機能要件：VC パネル色は保存や再表示に使える int 値へ正規化する。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))

    # When / Then
    assert service.normalize_color(discord.Color(0x123456)) == 0x123456
    assert service.normalize_color(0x654321) == 0x654321
    assert isinstance(service.normalize_color(None), int)


def test_tracks_message():
    """VC コントロールメッセージは channel ID ごとに message ID と色を記録する。"""
    # 機能要件：VC コントロールメッセージは channel ID ごとに追跡する。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))

    # When
    service.track_control_message(cast(Any, _Channel()), cast(Any, _Message()), color=0x123456)

    # Then
    assert service.control_panel_messages[100] == (55, 0x123456)


def test_untracks_message():
    """追跡解除は channel ID と message ID が一致した場合だけ状態を削除する。"""
    # 機能要件：VC コントロールメッセージは対応する message ID で追跡解除できる。
    # 非機能要件：異なる message ID の解除要求で追跡状態を誤削除しない。
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


def test_expires_name_rate_limit():
    """期限切れの VC 名変更 rate limit は状態から削除する。"""
    # 機能要件：期限切れの VC 名変更 rate limit は待機なしとして扱う。
    # 非機能要件：期限切れ rate limit を内部状態に残し続けない。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))
    service.name_change_rate_limited_until[100] = 0.0

    # When
    remaining = service.get_name_change_rate_limit_remaining(100)

    # Then
    assert remaining == 0.0
    assert service.name_change_rate_limited_until == {}


@pytest.mark.asyncio
async def test_extends_name_rate_limit(monkeypatch):
    """既存の VC 名変更 rate limit より短い retry_after では解除予定を短縮しない。"""
    # 非機能要件：追加の rate limit 通知で既存の解除予定を短縮しない。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))
    service.name_change_rate_limited_until[100] = 200.0

    async def refresh_control_panels(_channel: object) -> None:
        return None

    def create_task(coro: object) -> None:
        cast(Any, coro).close()

    monkeypatch.setattr("app.features.vc.service.time.monotonic", lambda: 100.0)
    monkeypatch.setattr(service, "refresh_control_panels", refresh_control_panels)
    monkeypatch.setattr("app.features.vc.service.asyncio.create_task", create_task)

    # When
    remaining = await service.disable_name_change_until_rate_limit_ends(
        cast(Any, _VoiceChannel()),
        cast(Any, _Actor()),
        retry_after=10.0,
    )

    # Then
    assert remaining == 100.0
    assert service.name_change_rate_limited_until[100] == 200.0

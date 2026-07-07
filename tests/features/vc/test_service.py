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
    name = "actor"


class _EditableVoiceChannel(_VoiceChannel):
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit(self, **kwargs: object) -> None:
        self.edits.append(kwargs)


class _RateLimitedVoiceChannel(_VoiceChannel):
    async def edit(self, **_: object) -> None:
        raise discord.RateLimited(10.0)


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


def test_expires_name_change_window(monkeypatch):
    """10 分窓を過ぎた VC 名変更履歴は rate limit 判定から除外する。"""
    # 機能要件：VC 名変更の 10 分窓を過ぎた履歴は新しい変更を妨げない。
    # 非機能要件：期限切れの名変更履歴を内部状態に残し続けない。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))
    service.name_change_timestamps[100] = [0.0, 1.0]
    monkeypatch.setattr("app.features.vc.service.time.monotonic", lambda: 601.0)

    # When
    remaining = service.get_name_change_rate_limit_remaining(100)

    # Then
    assert remaining == 0.0
    assert service.name_change_timestamps == {}


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


@pytest.mark.asyncio
async def test_rejects_name_change_during_rate_limit(monkeypatch):
    """VC 名変更待機中は Discord API を呼ばずに残り時間を返す。"""
    # 非機能要件：VC 名変更の rate limit 待機中は追加のチャンネル編集 API を発生させない。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))
    service.name_change_rate_limited_until[100] = 110.0
    channel = _EditableVoiceChannel()
    monkeypatch.setattr("app.features.vc.service.time.monotonic", lambda: 100.0)

    # When
    remaining = await service.rename_channel_with_rate_limit_handling(
        cast(Any, channel),
        cast(Any, _Actor()),
        "new-name",
    )

    # Then
    assert remaining == 10.0
    assert channel.edits == []


@pytest.mark.asyncio
async def test_allows_two_name_changes_per_window(monkeypatch):
    """VC 名変更は同一チャンネルで 10 分間に 2 回まで許可する。"""
    # 機能要件：VC 名変更は同一チャンネルで 10 分間に 2 回まで実行できる。
    # 非機能要件：3 回目以降は Discord API を呼ばずにローカルで待機状態として扱う。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))
    channel = _EditableVoiceChannel()

    async def refresh_control_panels(_channel: object) -> None:
        return None

    def create_task(coro: object) -> None:
        cast(Any, coro).close()

    monkeypatch.setattr("app.features.vc.service.time.monotonic", lambda: 100.0)
    monkeypatch.setattr(service, "refresh_control_panels", refresh_control_panels)
    monkeypatch.setattr("app.features.vc.service.asyncio.create_task", create_task)

    # When
    first_remaining = await service.rename_channel_with_rate_limit_handling(
        cast(Any, channel),
        cast(Any, _Actor()),
        "first-name",
    )
    second_remaining = await service.rename_channel_with_rate_limit_handling(
        cast(Any, channel),
        cast(Any, _Actor()),
        "second-name",
    )
    third_remaining = await service.rename_channel_with_rate_limit_handling(
        cast(Any, channel),
        cast(Any, _Actor()),
        "third-name",
    )

    # Then
    assert first_remaining is None
    assert second_remaining is None
    assert third_remaining == 600.0
    assert [edit["name"] for edit in channel.edits] == ["first-name", "second-name"]
    assert service.name_change_timestamps[100] == [100.0, 100.0]


@pytest.mark.asyncio
async def test_records_name_change_rate_limit(monkeypatch):
    """VC 名変更 API が rate limit に達した場合は待機状態として記録する。"""
    # 機能要件：VC 名変更が Discord rate limit に達した場合は retry_after を呼び出し元へ返す。
    # 非機能要件：rate limit 到達後は同じチャンネルの名前変更ボタンを待機状態にできるよう記録する。
    # Given
    service = VoiceCreateService(cast(Any, _Bot()))

    async def refresh_control_panels(_channel: object) -> None:
        return None

    def create_task(coro: object) -> None:
        cast(Any, coro).close()

    monkeypatch.setattr("app.features.vc.service.time.monotonic", lambda: 100.0)
    monkeypatch.setattr(service, "refresh_control_panels", refresh_control_panels)
    monkeypatch.setattr("app.features.vc.service.asyncio.create_task", create_task)

    # When
    remaining = await service.rename_channel_with_rate_limit_handling(
        cast(Any, _RateLimitedVoiceChannel()),
        cast(Any, _Actor()),
        "new-name",
    )

    # Then
    assert remaining == 10.0
    assert service.name_change_rate_limited_until[100] == 110.0

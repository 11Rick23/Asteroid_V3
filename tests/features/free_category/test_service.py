from __future__ import annotations

import time
from typing import Any, cast

from app.features.free_category.service import FreeCategoryService, decorate_int, get_free_category_service


class _FreeCategoryConfig:
    text_create_channel_id = 10
    text_create_channel_cooldown_seconds = 86400


class _Config:
    free_category = _FreeCategoryConfig()


class _Bot:
    config = _Config()
    services: dict[str, object] = {}


class _Channel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id


class _Category:
    def __init__(self, channels: list[_Channel]) -> None:
        self.channels = channels


def test_decorates_int():
    """順位表示用の数値は英語序数の例外を含めて変換する。"""
    # 機能要件：順位表示用の数値は英語序数へ変換する。
    # 非機能要件：11、12、13 などの例外値を誤った suffix にしない。
    # Given / When / Then
    assert decorate_int(1) == "1st"
    assert decorate_int(2) == "2nd"
    assert decorate_int(3) == "3rd"
    assert decorate_int(4) == "4th"
    assert decorate_int(11) == "11th"
    assert decorate_int(12) == "12th"
    assert decorate_int(13) == "13th"
    assert decorate_int(21) == "21st"


def test_filters_reserved():
    """managed_only のカテゴリ一覧では作成ボタン用チャンネルを除外する。"""
    # 機能要件：管理対象チャンネル一覧から作成ボタン用チャンネルを除外する。
    # Given
    service = FreeCategoryService(cast(Any, _Bot()))
    reserved = _Channel(10)
    normal = _Channel(20)
    category = _Category([reserved, normal])

    # When
    channels = service.get_channels_in_category(cast(Any, category), managed_only=True)

    # Then
    assert channels == [normal]
    assert service.get_free_category_min_position(cast(Any, category)) == 1


def test_expires_edit_cooldown():
    """編集クールダウンは期限切れになった時点で状態から削除する。"""
    # 機能要件：期限切れの編集クールダウンは待機なしとして扱う。
    # 非機能要件：期限切れ cooldown を内部状態に残し続けない。
    # Given
    service = FreeCategoryService(cast(Any, _Bot()))
    service.edit_cooldowns[123] = time.monotonic() - 1

    # When
    retry_after = service.get_edit_cooldown_retry_after(123)

    # Then
    assert retry_after == 0.0
    assert 123 not in service.edit_cooldowns


def test_reuses_bot_service():
    """free_category service は bot の共有 service registry から再利用する。"""
    # 機能要件：free_category service は bot ごとに同じインスタンスを再利用する。
    # 非機能要件：呼び出しごとに cooldown 状態を失う新規 service を作らない。
    # Given
    bot = _Bot()

    # When
    first = get_free_category_service(cast(Any, bot))
    second = get_free_category_service(cast(Any, bot))

    # Then
    assert second is first
    assert bot.services["free_category"] is first

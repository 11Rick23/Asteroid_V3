from __future__ import annotations

from app.core.config import AsteroidConfig, FeatureFlags
from app.core.extensions import FEATURE_EXTENSION_MAP, iter_enabled_extensions


def test_maps_all_flags():
    """拡張機能マップは FeatureFlags の全項目と過不足なく対応する。"""
    # 非機能要件：feature flag と extension map の不整合で機能の有効化漏れを起こさない。
    # Given
    flag_names = set(FeatureFlags.model_fields)
    mapped_names = {flag_name for flag_name, _ in FEATURE_EXTENSION_MAP}

    # When / Then
    assert mapped_names == flag_names


def test_skips_disabled_feature():
    """無効化された feature は読み込み対象の extension から除外される。"""
    # 機能要件：無効化した feature の extension は起動時に読み込まれない。
    # Given
    config = AsteroidConfig(features=FeatureFlags(rolepanel=False))

    # When
    extensions = list(iter_enabled_extensions(config))

    # Then
    assert "app.features.rolepanel.cog" not in extensions
    assert "app.features.auth.cog" in extensions

from __future__ import annotations

import logging

from app.core.config import AsteroidConfig
from app.core.extensions import iter_enabled_extensions


def test_iter_enabled_extensions_loads_leveling_once() -> None:
    feature_flags = dict.fromkeys(AsteroidConfig().features.model_dump(), False)
    feature_flags["leveling"] = True

    config = AsteroidConfig.model_validate({"features": feature_flags})

    assert list(iter_enabled_extensions(config)) == ["app.features.leveling.cog"]


def test_iter_enabled_extensions_logs_feature_decisions(caplog) -> None:
    feature_flags = dict.fromkeys(AsteroidConfig().features.model_dump(), False)
    feature_flags["leveling"] = True
    config = AsteroidConfig.model_validate({"features": feature_flags})

    with caplog.at_level(logging.DEBUG, logger="app.core.extensions"):
        assert list(iter_enabled_extensions(config)) == ["app.features.leveling.cog"]

    assert "feature=leveling enabled=True" in caplog.text
    assert "feature=auth enabled=False" in caplog.text

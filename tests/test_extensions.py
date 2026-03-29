from __future__ import annotations

from app.core.config import AsteroidConfig
from app.core.extensions import iter_enabled_extensions


def test_iter_enabled_extensions_loads_leveling_once() -> None:
    feature_flags = dict.fromkeys(AsteroidConfig().features.model_dump(), False)
    feature_flags["leveling"] = True

    config = AsteroidConfig.model_validate({"features": feature_flags})

    assert list(iter_enabled_extensions(config)) == ["app.features.leveling.cog"]

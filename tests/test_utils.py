from __future__ import annotations

import pytest

from app.common.utils import fire_and_forget


@pytest.mark.asyncio
async def test_fire_and_forget_supports_keyword_arguments() -> None:
    def build_message(name: str, *, suffix: str) -> str:
        return f"{name}-{suffix}"

    wrapped = fire_and_forget(build_message)

    result = await wrapped("asteroid", suffix="v3")

    assert result == "asteroid-v3"

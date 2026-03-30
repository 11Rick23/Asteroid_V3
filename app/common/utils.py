from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any


def generate_timestamp() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def fire_and_forget[**P, R](func: Callable[P, R]) -> Callable[P, Any]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, partial(func, *args, **kwargs))

    return wrapper


def humanize_number(number: int) -> str:
    if number < 1_000:
        return str(number)
    if number < 10_000:
        return f"{round(number / 1_000, 2)}K"
    if number < 100_000:
        return f"{round(number / 1_000, 1)}K"
    if number < 1_000_000:
        return f"{number // 1_000}K"
    if number < 10_000_000:
        return f"{round(number / 1_000_000, 2)}M"
    if number < 100_000_000:
        return f"{round(number / 1_000_000, 1)}M"
    if number < 1_000_000_000:
        return f"{number // 1_000_000}M"
    if number < 10_000_000_000:
        return f"{round(number / 1_000_000_000, 2)}B"
    if number < 100_000_000_000:
        return f"{round(number / 1_000_000_000, 1)}B"
    if number < 1_000_000_000_000:
        return f"{number // 1_000_000_000}B"
    if number < 10_000_000_000_000:
        return f"{round(number / 1_000_000_000_000, 2)}T"
    if number < 100_000_000_000_000:
        return f"{round(number / 1_000_000_000_000, 1)}T"
    if number < 1_000_000_000_000_000:
        return f"{number // 1_000_000_000_000}T"
    return f"{number // 1_000_000_000_000_000}Q"

from __future__ import annotations

import re
from datetime import timedelta

_DURATION_PATTERN = re.compile(r"\s*([0-9]+)\s*([wdhms])", re.IGNORECASE)
_SECONDS_BY_UNIT = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_boost_duration(value: str) -> timedelta | None:
    seconds = 0
    position = 0
    for match in _DURATION_PATTERN.finditer(value):
        if match.start() != position:
            return None
        try:
            seconds += int(match.group(1)) * _SECONDS_BY_UNIT[match.group(2).lower()]
        except ValueError:
            return None
        position = match.end()
    if value[position:].strip() or seconds <= 0:
        return None
    try:
        return timedelta(seconds=seconds)
    except OverflowError:
        return None

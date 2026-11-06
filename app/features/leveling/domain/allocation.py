from __future__ import annotations

from collections.abc import Mapping

from .numbers import MAX_DURATION_US, amount, identifier, integer


def allocate_power(power: int, durations: Mapping[int, int]) -> dict[int, int]:
    """最大剰余法。剰余同率はチャンネルID昇順で決定する。"""
    amount(power)
    for channel_id, duration in durations.items():
        identifier(channel_id)
        integer(duration, maximum=MAX_DURATION_US)
    total = sum(durations.values())
    if not total:
        if power:
            raise ValueError("正のパワーには有効滞在時間が必要です")
        return dict.fromkeys(sorted(durations), 0)
    parts = {key: divmod(power * duration, total) for key, duration in durations.items()}
    result = {key: parts[key][0] for key in sorted(parts)}
    for key in sorted(parts, key=lambda key: (-parts[key][1], key))[: power - sum(result.values())]:
        result[key] += 1
    return result

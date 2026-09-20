from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager


class LevelingLocks:
    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._monthly_power_reset_requested = False
        self._resetting_monthly_power = False
        self._active_user_updates = 0
        self._user_locks: dict[int, asyncio.Lock] = {}

    @asynccontextmanager
    async def user_updates(self, *user_ids: int) -> AsyncIterator[None]:
        async with self._condition:
            while self._monthly_power_reset_requested or self._resetting_monthly_power:
                await self._condition.wait()
            self._active_user_updates += 1

        try:
            async with AsyncExitStack() as stack:
                for user_id in sorted(set(user_ids)):
                    await stack.enter_async_context(self._user_locks.setdefault(user_id, asyncio.Lock()))
                yield
        finally:
            async with self._condition:
                self._active_user_updates -= 1
                if self._active_user_updates == 0:
                    self._condition.notify_all()

    @asynccontextmanager
    async def _monthly_power_reset(self) -> AsyncIterator[None]:
        requested = False
        try:
            async with self._condition:
                while self._monthly_power_reset_requested or self._resetting_monthly_power:
                    await self._condition.wait()
                self._monthly_power_reset_requested = True
                requested = True
                while self._active_user_updates > 0:
                    await self._condition.wait()
                self._resetting_monthly_power = True
            yield
        finally:
            if requested:
                async with self._condition:
                    self._resetting_monthly_power = False
                    self._monthly_power_reset_requested = False
                    self._condition.notify_all()

    def _user_update(self, user_id: int):
        return self.user_updates(user_id)

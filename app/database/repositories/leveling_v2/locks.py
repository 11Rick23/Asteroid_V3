"""全P2 writerで共有する公平なmutation gate。ロックの再入・昇格は禁止。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar

_held: ContextVar[bool] = ContextVar("leveling_v2_gate_held", default=False)


class MutationGate:
    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._readers = 0
        self._writer = False
        self._waiting_writers = 0
        self._users: dict[int, asyncio.Lock] = {}
        self._coordinator = asyncio.Lock()

    @asynccontextmanager
    async def shared(self, *users: int, coordinator: bool = False) -> AsyncIterator[None]:
        if _held.get():
            raise RuntimeError("mutation gateの再入取得は禁止です")
        async with self._condition:
            await self._condition.wait_for(lambda: not self._writer and not self._waiting_writers)
            self._readers += 1
        token = _held.set(True)
        try:
            async with AsyncExitStack() as stack:
                if coordinator:
                    await stack.enter_async_context(self._coordinator)
                for user in sorted(set(users)):
                    await stack.enter_async_context(self._users.setdefault(user, asyncio.Lock()))
                yield
        finally:
            _held.reset(token)
            async with self._condition:
                self._readers -= 1
                self._condition.notify_all()

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[None]:
        if _held.get():
            raise RuntimeError("mutation gateの再入取得・昇格は禁止です")
        async with self._condition:
            self._waiting_writers += 1
            try:
                await self._condition.wait_for(lambda: not self._writer and self._readers == 0)
                self._writer = True
            finally:
                self._waiting_writers -= 1
                self._condition.notify_all()
        token = _held.set(True)
        try:
            yield
        finally:
            _held.reset(token)
            async with self._condition:
                self._writer = False
                self._condition.notify_all()

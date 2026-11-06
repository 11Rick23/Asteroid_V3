"""セッションを跨ぐ再試行。commit応答喪失は結果照会が成功するまで再実行しない。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar, cast

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class DuplicateOperation(RuntimeError):
    pass


class VersionConflict(RuntimeError):
    pass


class OperationConflict(VersionConflict):
    """競合後に永久操作キーを別snapshotで再確認してからversion不一致を返す。"""


class CommitUnknown(RuntimeError):
    """呼出し側は同一キーの照会成功まで新しい命令を発行しない。"""


@dataclass(frozen=True)
class Resolution[T]:
    found: bool
    value: T | None = None


def mysql_error_code(error: DBAPIError) -> int | None:
    args = getattr(error.orig, "args", ())
    return args[0] if args and type(args[0]) is int else None


class Transactions:
    def __init__(self, sessions: Callable[[], AsyncSession]) -> None:
        self.sessions = sessions

    async def run(
        self,
        action: Callable[[AsyncSession], Awaitable[T]],
        resolve: Callable[[AsyncSession], Awaitable[Resolution[T]]],
    ) -> T:
        for attempt in range(3):
            committing = False
            try:
                async with self.sessions() as session:
                    try:
                        result = await action(session)
                        await session.flush()
                        committing = True
                        await session.commit()
                        return result
                    except BaseException:
                        # close時のrollbackだけに依存しない。接続障害ならinvalidateする。
                        try:
                            await session.rollback()
                        except BaseException:
                            await session.invalidate()
                        raise
            except (DuplicateOperation, OperationConflict) as conflict:
                try:
                    async with self.sessions() as probe:
                        resolution = await resolve(probe)
                        await probe.rollback()
                except Exception as error:
                    raise CommitUnknown("競合操作の確定結果を照会できません") from error
                if not resolution.found:
                    if isinstance(conflict, OperationConflict):
                        raise VersionConflict(str(conflict)) from conflict
                    raise CommitUnknown("重複操作の結果を確認できません") from None
                return cast(T, resolution.value)
            except DBAPIError as error:
                code = mysql_error_code(error)
                if code in (1205, 1213):
                    if attempt == 2:
                        raise
                    continue
                if committing or isinstance(error, IntegrityError):
                    try:
                        async with self.sessions() as probe:
                            resolution = await resolve(probe)
                            await probe.rollback()
                    except Exception as probe_error:
                        raise CommitUnknown("DB確定結果を照会できません。同じキーの再確認が必要です") from probe_error
                    if resolution.found:
                        # found=TrueはNoneを有効な返却値とする操作も含む。
                        return cast(T, resolution.value)
                    if committing:
                        # 非存在の1回の読取だけで、遅延commitの不在を断定しない。
                        raise CommitUnknown("DB確定結果を確認できません。同じキーの再確認が必要です") from error
                raise
        raise AssertionError("unreachable")

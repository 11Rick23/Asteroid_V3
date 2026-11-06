"""永続数値の境界検査。中間演算は格納範囲で丸めない。"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

MAX_AMOUNT = 10**65 - 1
MAX_ID = 2**64 - 1
MAX_DURATION_US = 2**63 - 1


def integer(value: int, *, minimum: int = 0, maximum: int = MAX_AMOUNT) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("整数値が許容範囲外です")
    return value


def amount(value: int) -> int:
    return integer(value)


def identifier(value: int) -> int:
    return integer(value, minimum=1, maximum=MAX_ID)


def total_amount(*values: int) -> int:
    return amount(sum(amount(value) for value in values))


def coefficient(value: Decimal) -> Fraction:
    """Decimalのコンテキストに依存せず有限非負の係数を整数比へ変換する。"""
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("係数は有限の非負Decimalで指定してください")
    return Fraction(value)


def boolean(value: bool) -> bool:
    if type(value) is not bool:
        raise ValueError("真偽値を指定してください")
    return value

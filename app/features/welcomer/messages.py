from __future__ import annotations


def first_welcome(*, prefix: str, member_mention: str) -> str:
    return f"{prefix}{member_mention}さん、ナメック星へようこそ！"


def return_welcome(*, prefix: str, member_mention: str) -> str:
    return f"{prefix}{member_mention}さん、お帰りなさい！"

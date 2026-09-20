from __future__ import annotations

USER_LABEL = "ユーザー"
ROLE_NOT_FOUND = "ロールが見つかりません"
RANKING_NO_DATA = "ランキングデータはありません。"
PREVIOUS_PAGE_LABEL = "<"
NEXT_PAGE_LABEL = ">"


def unknown_member(*, user_id: int) -> str:
    return f"不明なメンバー [{user_id}]"


def ranking_position(*, ranking: int) -> str:
    medals = ("🥇", "🥈", "🥉")
    return medals[ranking - 1] if 1 <= ranking <= len(medals) else f"{ranking}位"


def ranking_header(*, title: str, description: str) -> str:
    return f"# {title}\n{description}"

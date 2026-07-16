from __future__ import annotations

LEVEL_UP_TITLE = "レベルアップ！"
PRESTIGE_UP_TITLE = "プレステージ！"
PRESTIGE_ACHIEVEMENT_TITLE = "プレステージ達成！"


def grade_up(*, author_mention: str, old_grade: int, new_grade: int) -> str:
    return f"{author_mention}さんがGrade. {old_grade}からGrade. {new_grade}へグレードアップ！"


def prestige_up(*, author_mention: str, old_prestige: int, new_prestige: int) -> str:
    return f"{author_mention}さんがPrestige. {old_prestige}からPrestige. {new_prestige}へプレステージ！"


def prestige_achievement(*, member_mention: str, achievement: str) -> str:
    return f"{member_mention}さんが{achievement}を達成しました！\nおめでとうございます！"


def prestige_name(*, prestige: int) -> str:
    return f"プレステージ{prestige}"

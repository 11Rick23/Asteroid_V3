from __future__ import annotations

BIRTHDAY_EMOJI = "🎂"
BIRTHDAY_GROUP_DESCRIPTION = "誕生日に関するコマンド"
SET_DESCRIPTION = "誕生日を設定"
SET_OTHERS_DESCRIPTION = "他人の誕生日を設定"
SHOW_DESCRIPTION = "誕生日を表示"
REMOVE_DESCRIPTION = "誕生日を削除"
LIST_DESCRIPTION = "次の誕生日10人をリスト形式で表示"
USER_LABEL = "ユーザー"
MONTH_LABEL = "月"
DAY_LABEL = "日"
BIRTHDAY_MONTH_DESCRIPTION = "誕生日の月"
BIRTHDAY_DAY_DESCRIPTION = "誕生日の日"
SET_USER_DESCRIPTION = "設定するユーザー"
SHOW_USER_DESCRIPTION = "誕生日を表示するユーザー"
REMOVE_USER_DESCRIPTION = "誕生日を削除するユーザー"
REMOVE_OTHERS_PERMISSION_REQUIRED = "管理者権限を持っていない場合、`user` オプションは使用できません。"
NO_BIRTHDAYS = "まだ誰も誕生日を設定していません。"
BIRTHDAY_LIST_TITLE = f"{BIRTHDAY_EMOJI} 誕生日リスト"
TODAY = "今日"
TOMORROW = "明日"
DAY_AFTER_TOMORROW = "明後日"
DATE_FORMAT = "%Y年%m月%d日"


def birthday_announcement(*, member_mention: str) -> str:
    return f"# 今日は {member_mention} の誕生日だ！おめでとう！{BIRTHDAY_EMOJI}"


def invalid_birthday(*, month: int, day: int) -> str:
    return f"`{month}/{day}` は存在しません。"


def birthday_set_message(*, month: int, day: int) -> str:
    return f"誕生日を `{month}/{day}` に設定しました。"


def other_birthday_set(*, user_mention: str, month: int, day: int) -> str:
    return f"{user_mention} の誕生日を `{month}/{day}` に設定しました。"


def birthday_not_set(*, user_mention: str) -> str:
    return f"{user_mention} はまだ誕生日を設定していません。"


def birthday_details(*, user_mention: str, month: int, day: int) -> str:
    return f"{user_mention} の誕生日は `{month}/{day}` です。"


def birthday_removed(*, user_mention: str) -> str:
    return f"{user_mention} の誕生日を削除しました。"

from __future__ import annotations

DISSOKU_REMINDER_TITLE = "前回のディス速のUPから2時間経過しました！"
DISSOKU_REMINDER_DESCRIPTION = "</up:1363739182672904354>を実行しよう！"
DICOALL_REMINDER_TITLE = "前回のDicoallのUPから1時間経過しました！"
DICOALL_REMINDER_DESCRIPTION = "</up:935190259111706754>を実行しよう！"
BUMP_REMINDER_TITLE = "前回のBumpから2時間経過しました！"
BUMP_REMINDER_DESCRIPTION = "</bump:947088344167366698>を実行しよう！"
DISSOKU_THANKS_SERVICE = "ディス速のUP"
DICOALL_THANKS_SERVICE = "DicoallのUP"
BUMP_THANKS_SERVICE = "Bump"
UP_SERVICE = "UP"
BUMP_SERVICE = "BUMP"


def thanks_title(*, display_name: str, service_name: str) -> str:
    return f"{display_name}さん、{service_name}ありがとう！"


def next_notice_description(*, relative_time: str, service_name: str) -> str:
    return f"{relative_time}にこのチャンネルで{service_name}通知を行います"


def rta_title(*, service_name: str) -> str:
    return f"{service_name} RTAが行われました！"


def rta_description(*, service_name: str, elapsed_seconds: float) -> str:
    return f"{service_name}通知から{elapsed_seconds}秒で{service_name}が行われました"

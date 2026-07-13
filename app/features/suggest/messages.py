from __future__ import annotations

GROUP_DESCRIPTION = "要望に関するコマンド"
REASON_FIELD_NAME = "理由"
FORUM_THREAD_ONLY = "このコマンドは要望フォーラム下のスレッドにのみ使用できます。"
THREAD_ONLY = "このコマンドはスレッドでのみ実行できます。"
APPROVE_DESCRIPTION = "要望を可決"
DENY_DESCRIPTION = "要望を否決"
REASON_LABEL = "理由"
APPROVE_REASON_DESCRIPTION = "要望を可決する理由"
DENY_REASON_DESCRIPTION = "要望を否決する理由"
APPROVED = "可決"
DENIED = "否決"


def result_title(*, judgment: str) -> str:
    return f"この要望は{judgment}されました"

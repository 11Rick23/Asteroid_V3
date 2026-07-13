from __future__ import annotations

GROUP_DESCRIPTION = "処罰コマンド"
TARGET_USER_LABEL = "対象ユーザー"
REPORT_CONTENT_LABEL = "レポート内容"
REASON_LABEL = "理由"
DURATION_LABEL = "期間"
PROBATION_LABEL = "執行猶予"
NONE_DESCRIPTION = "処罰: 無し"
LECTURE_DESCRIPTION = "処罰: 口頭注意"
DELETE_DESCRIPTION = "処罰: メッセージ削除"
TIMEOUT_DESCRIPTION = "処罰: タイムアウト"
DISROBE_DESCRIPTION = "処罰: 権限剥奪"
MUTE_DESCRIPTION = "処罰: MUTE"
FORBID_DESCRIPTION = "処罰: 閲覧禁止"
BAN_DESCRIPTION = "処罰: BAN"
PUNISHMENT_NONE = "無し"
PUNISHMENT_LECTURE = "口頭注意"
PUNISHMENT_DELETE = "メッセージ削除"
PUNISHMENT_TIMEOUT = "タイムアウト"
PUNISHMENT_DISROBE = "権限剥奪"
PUNISHMENT_MUTE = "MUTE"
PUNISHMENT_FORBID = "閲覧禁止"
PUNISHMENT_BAN = "BAN"
SENT = "送信完了です！"
TIMEOUT_TOO_LONG = "指定された時間は長すぎます！\nタイムアウトできる最長の期間は28日間（4週間）です。"
GUILD_ONLY = "サーバー内でのみ使用できます。"
NO_DISROBE_ROLES = "剥奪対象の権限ロールが見つかりませんでした。"
DISROBE_PLACEHOLDER = "剥奪する権限ロールを選択…"
PERMISSION_REQUIRED = "この操作を実行する権限がありません。"
PUNISHMENT_BOARD_NOT_FOUND = "処罰板チャンネルが見つかりません。"
TIMEOUT_MEMBER_NOT_FOUND_WARNING = (
    "\n:warning:メンバーが見つからなかったためタイムアウト・前科ロールの付与をできませんでした！"
)
MUTE_MEMBER_NOT_FOUND_WARNING = (
    "\n:warning:メンバーが見つからなかったため前科ロール・MUTEロールの付与をできませんでした！"
)
FORBID_MEMBER_NOT_FOUND_WARNING = (
    "\n:warning:メンバーが見つからなかったため前科ロール・閲覧禁止ロールの付与をできませんでした！"
)
CRIME_ROLE_MEMBER_NOT_FOUND_WARNING = "\n:warning:メンバーが見つからなかったため前科ロールを付与できませんでした！"


def invalid_timeout_duration(*, duration: str) -> str:
    return f"`{duration}`は無効なフォーマットです！\n対応する単位は: w, d, h, m, s"


def disrobe_prompt(*, target_mention: str) -> str:
    return f"{target_mention} からどの権限を剥奪しますか？"


def no_punishment_record(*, user_name: str, date_text: str, content: str, reason: str) -> str:
    return f"```{user_name}\n日付: {date_text}\nレポート内容: {content}\n処罰: 無し\n理由: {reason}```"


def punishment_record(
    *,
    user_name: str,
    user_id: int,
    date_text: str,
    reason: str,
    punishment: str,
    probation: str | None,
    duration: str | None,
) -> str:
    return (
        f"```{user_name} {user_id}\n"
        f"日付: {date_text}\n"
        f"違反内容: {reason}\n"
        f"処罰: {punishment}"
        + (f"\n期間: {duration}" if duration is not None else "")
        + (f"\n執行猶予: {probation}```" if probation is not None else "```")
    )


def disrobe_punishment(*, role_names: list[str]) -> str:
    return f"権限剥奪 {role_names}"

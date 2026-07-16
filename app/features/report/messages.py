from __future__ import annotations

COMMAND_DESCRIPTION = "レポートを送信"
VIOLATOR_LABEL = "対象ユーザー"
CONTENT_LABEL = "違反内容"
IMAGE_LABEL = "画像"
VIOLATOR_DESCRIPTION = "レポートするユーザー"
CONTENT_DESCRIPTION = "違反した内容を詳しく書いて下さい。"
IMAGE_DESCRIPTION = "違反内容の画像などがあれば添付して下さい。"
SENDING = "レポート送信中…"
GUILD_ONLY = "サーバー内でのみ使用できます。"
DESTINATION_NOT_FOUND = "レポート送信先チャンネルが見つかりませんでした。"
COMPLETED = "レポート送信完了。\nレポートありがとうございました。"
UNRESOLVED = "未対応"
RESOLVE_BUTTON_LABEL = "対応完了"
RESOLVE_PERMISSION_REQUIRED = "この操作を実行する権限がありません。"
REPORT_NOT_FOUND = "レポート情報が見つかりませんでした。"


def destination_content(*, prefix: str, violator_mention: str) -> str:
    return f"{prefix}レポートされたユーザー: {violator_mention}"


def resolved_by(*, moderator_display_name: str) -> str:
    return f"{moderator_display_name} によって対応済み"

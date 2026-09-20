from __future__ import annotations

LOGIN_TITLE = "ログイン完了！"
LOGIN_ID_FIELD_NAME = "ID"
LOGIN_CREATED_AT_FIELD_NAME = "作成日時 (JST)"
MISSING_USER_PERMISSIONS = "権限が足りません！"
MISSING_BOT_PERMISSIONS = "コマンドを実行するのにBOTに必要な権限がありません！"
INVALID_ARGUMENT = "渡された引数が無効です！"
COMMAND_PERMISSION_REQUIRED = "このコマンドを実行する権限がありません。"
APP_COMMAND_ERROR_TITLE = "アプリコマンドエラー"
COMMAND_FIELD_NAME = "コマンド"
USER_FIELD_NAME = "ユーザー"
GUILD_CHANNEL_FIELD_NAME = "サーバー / チャンネル"


def login_description(*, bot_user: str) -> str:
    return f"`{bot_user}`としてログインしました。"


def command_cooldown(*, retry_after: float) -> str:
    return f"コマンドはクールダウン中です！\n`{round(retry_after, 2)}秒後`に再度試してください。"

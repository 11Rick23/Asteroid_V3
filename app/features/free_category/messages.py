from __future__ import annotations

GROUP_DESCRIPTION = "フリーカテゴリーに関するコマンド"
ARCHIVE_DESCRIPTION = "チャンネルをアーカイブ"
EDIT_DESCRIPTION = "チャンネル情報を変更"
BLOCK_DESCRIPTION = "指定したユーザーをブロック"
UNBLOCK_DESCRIPTION = "指定したユーザーのブロックを解除"
OP_DESCRIPTION = "指定したユーザーにチャンネルの管理権限を付与"
DEOP_DESCRIPTION = "指定したユーザーからチャンネルの管理権限を剥奪"
PURGE_DESCRIPTION = "指定した件数メッセージを削除"
CHANNEL_NAME_LABEL = "チャンネル名"
TOPIC_LABEL = "トピック"
NAME_FIELD = "name"
TOPIC_FIELD = "topic"
USER_LABEL = "ユーザー"
COUNT_LABEL = "件数"
NEW_CHANNEL_NAME_DESCRIPTION = "新しいチャンネル名"
NEW_TOPIC_DESCRIPTION = "新しいチャンネルトピック"
BLOCK_USER_DESCRIPTION = "チャンネルを閲覧できなくするユーザー"
UNBLOCK_USER_DESCRIPTION = "チャンネル閲覧不可を解除するユーザー"
OP_USER_DESCRIPTION = "チャンネルの管理権限を付与するユーザー"
DEOP_USER_DESCRIPTION = "チャンネルの管理権限を剥奪するユーザー"
PURGE_COUNT_DESCRIPTION = "削除するメッセージの件数"
ARCHIVE_COMMAND_REASON = "運営、またはチャンネル管理者による `/fc archive` コマンド"
ARCHIVED = "チャンネルをアーカイブしました。"
EDIT_VALUE_REQUIRED = "チャンネル名かチャンネルトピックのどちらか一方は必ず入力してください。"
TOPIC_UNSET = "未設定"
NAME_CHANGED_TITLE = "チャンネル名を変更しました！"
TOPIC_CHANGED_TITLE = "チャンネルトピックを変更しました！"
NAME_TOPIC_CHANGED_TITLE = "チャンネル名とトピックを変更しました！"
CREATE_MODAL_TITLE = "チャンネルを作成"
CREATE_BUTTON_LABEL = "チャンネルを作成"
CREATE_PANEL_TITLE = "# 新しいフリーチャンネルの作成"
TEXT_CHANNEL_ONLY = "このコマンドはテキストチャンネルでのみ使えます。"
CHANNEL_MANAGER_REQUIRED = "あなたはこのチャンネルの管理者ではありません。"
ARCHIVED_TITLE = "このチャンネルはアーカイブ行きになりました。"
ARCHIVE_REASON_FIELD = "理由"
MINOR_BOTTOM_ARCHIVE_REASON = "マイナーカテゴリーの最下部に位置するため。"
GUILD_ONLY = "サーバー内でのみ利用できます。"
CHANNEL_NAME_REQUIRED = "チャンネル名を入力してください。"
ARCHIVE_CATEGORY_NOT_CONFIGURED = "`fc_archive_category_id` が未設定です。"
FREE_CATEGORY_NOT_CONFIGURED = "`free_category_id` が未設定です。"
MINOR_CATEGORY_NOT_CONFIGURED = "`minor_category_id` が未設定です。"
BUMPED_TITLE = "チャンネルがBUMPされました！"
PROMOTION_TITLE = "おめでとうございます！"
PANEL_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、フリーチャンネル作成機能は現在利用できません。時間を空けてもう一度ご確認ください。"
)


def edit_cooldown(*, retry_after: float) -> str:
    return f"このチャンネルの編集はクールダウン中です。`{round(retry_after, 1)}秒後`に再試行してください。"


def changed_value(*, old_value: str, new_value: str) -> str:
    return f"`{old_value}` -> `{new_value}`"


def user_blocked(*, display_name: str) -> str:
    return f"`{display_name}` をブロックしました！"


def user_unblocked(*, display_name: str) -> str:
    return f"`{display_name}` のブロックを解除しました！"


def user_opped(*, display_name: str) -> str:
    return f"`{display_name}` にチャンネルの管理権限を付与しました！"


def user_deopped(*, display_name: str) -> str:
    return f"`{display_name}` からチャンネルの管理権限を剥奪しました！"


def messages_purged(*, count: int) -> str:
    return f"{count}件のメッセージを削除しました！"


def channel_created(*, channel_mention: str) -> str:
    return f"{channel_mention} を作成しました！"


def created_channel_content(*, creator_mention: str, created_at: str) -> str:
    return (
        "# 新たなチャンネルが誕生しました…！\n"
        f"{creator_mention} のフリーチャンネルです。\n"
        "チャンネルを盛り上げよう！\n"
        f"\n-# 作成日時 : {created_at}"
    )


def create_cooldown(*, cooldown_hours: float) -> str:
    return f"チャンネル作成には {cooldown_hours:g} 時間のクールダウンがあります。"


def channel_topic(*, creator_mention: str, created_at: str) -> str:
    return f"{creator_mention} のチャンネルです！ \n作成日時 : {created_at}"


def hall_of_fame_message(*, channel_mention: str) -> str:
    return f"{channel_mention} は殿堂入りしました！"


def promoted(*, channel_mention: str) -> str:
    return f"{channel_mention} はフリーカテゴリーに昇格しました！"

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessageCopy:
    title: str
    description: str


GROUP_DESCRIPTION = "ロールパネル管理コマンド"
CATEGORY_GROUP_DESCRIPTION = "カテゴリ管理"
CATEGORY_ADD_DESCRIPTION = "ロールパネルカテゴリを追加します"
CATEGORY_EDIT_DESCRIPTION = "ロールパネルカテゴリを編集します"
CATEGORY_REMOVE_DESCRIPTION = "ロールパネルカテゴリを削除します"
EDIT_ROLE_DESCRIPTION = "カテゴリ内ロールを編集します"
REQUIRE_BOOST_DESCRIPTION = "カテゴリのロールをブースター限定設定を変更します。"
REFRESH_DESCRIPTION = "ロールパネルを再描画します"
LIST_DESCRIPTION = "ロールパネル設定を一覧表示します"
CATEGORY_LABEL = "カテゴリ"
CATEGORY_NAME_LABEL = "カテゴリ名"
DESCRIPTION_LABEL = "説明文"
ORDER_LABEL = "表示順"
BOOST_REQUIRED_LABEL = "ブースター限定"
ADD_CATEGORY_NAME_DESCRIPTION = "追加するカテゴリ名"
ADD_CATEGORY_DESCRIPTION_DESCRIPTION = "パネルに表示するカテゴリの説明文"
ADD_CATEGORY_ORDER_DESCRIPTION = "カテゴリの表示順。小さい値ほど先に表示されます"
EDIT_CATEGORY_DESCRIPTION = "編集するカテゴリ"
EDIT_CATEGORY_NAME_DESCRIPTION = "変更後のカテゴリ名"
EDIT_CATEGORY_DESCRIPTION_DESCRIPTION = "パネルに表示する変更後の説明文"
EDIT_CATEGORY_ORDER_DESCRIPTION = "変更後の表示順。小さい値ほど先に表示されます"
REMOVE_CATEGORY_DESCRIPTION = "削除するカテゴリ"
EDIT_ROLE_CATEGORY_DESCRIPTION = "ロールを編集するカテゴリ"
REQUIRE_BOOST_CATEGORY_DESCRIPTION = "設定を変更するカテゴリ"
REQUIRE_BOOST_VALUE_DESCRIPTION = "ブースター限定にするかどうか"
CATEGORY_NO_CHANGES = MessageCopy("変更内容がありません", "変更内容を1つ以上指定してください。")
CATEGORY_NOT_FOUND = MessageCopy("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。")
CATEGORY_REMOVED = MessageCopy("カテゴリを削除しました", "カテゴリを削除しました。")
ROLE_EDIT_PERMISSION_REQUIRED = MessageCopy("権限がありません", "この操作を実行する権限がありません。")
GUILD_EXECUTION_REQUIRED = MessageCopy("実行できません", "サーバー内で実行してください。")
GUILD_ONLY = MessageCopy("実行できません", "サーバー内でのみ使用できます。")
ROLE_UPDATED_TITLE = "ロールを更新しました"
ROLE_SELECT_OWNER_ONLY = MessageCopy("操作できません", "このロール選択画面はあなた専用です。")
ROLE_SYNCED_TITLE = "ロールを同期しました"
ROLE_SYNCED = "ロールを同期しました。"
BOOST_REQUIRED_MODAL_TITLE = "ブースター専用ロール"
BOOST_REQUIRED_MODAL_CONTENT = "このカテゴリのロールを入手するにはサーバーをブーストする必要があります。"
ROLE_SELECT_BUTTON_LABEL = "ロールを選択"
CATEGORY_MISSING = MessageCopy("カテゴリが見つかりません", "このカテゴリは存在しません。")
ROLE_UNSET = MessageCopy("ロール未設定", "このカテゴリには選択可能なロールが設定されていません。")
PANEL_CONTENT = "# 🎭 ロールパネル\nカテゴリごとのボタンから、付け外ししたいロールを選択してください。"
PANEL_CATEGORY_UNSET = "### カテゴリ未設定\n管理者がカテゴリを追加するまで利用できません。"
DESCRIPTION_UNSET = "説明未設定"
BOOST_REQUIRED_NOTE = "-# サーバーブースター限定"
PANEL_TITLE = "ロールパネル"
PANEL_DESCRIPTION = "カテゴリを選択して、付け外ししたいロールを選んでください。"
CATEGORY_UNSET_FIELD = "カテゴリ未設定"
CATEGORY_UNSET_DESCRIPTION = "管理者がカテゴリを追加するまで利用できません。"
CATEGORY_SETTINGS_TITLE = "ロールパネルカテゴリ設定一覧"
NO_CATEGORIES = "カテゴリはまだ登録されていません。"
CATEGORY_SETTINGS_PREFIX = "表示順: `{display_order}`\n説明文:\n"
SYNC_GUILD_ONLY = "サーバー内でのみ使用できます。"
SYNC_CATEGORY_MISSING = "このカテゴリは存在しません。"
SYNC_BOOST_REQUIRED = "このカテゴリを利用するにはサーバーをブーストする必要があります。"
SYNC_UNMANAGEABLE_ROLE = "一部のロールはBOTの権限またはロール順により操作できませんでした。"
ROLE_MANAGE_GUILD_REQUIRED = "サーバー内で実行してください。"
ROLE_MANAGE_EVERYONE_REJECTED = "@everyone はロールパネルに登録できません。"
ROLE_MANAGE_MANAGED_REJECTED = "BOTや外部連携により管理されているロールは登録できません。"
ROLE_MANAGE_UNMANAGEABLE = "このロールはBOTから操作できません。BOTのロール順と権限を確認してください。"
ADMIN_ROLE_SELECT_PLACEHOLDER = "カテゴリに表示するロールを選択"
ROLE_PANEL_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、ロールパネルは現在利用できません。時間を空けてもう一度ご確認ください。"
)


def category_added(*, category_name: str) -> MessageCopy:
    return MessageCopy("カテゴリを追加しました", f"カテゴリ `{category_name}` を追加しました。")


def category_updated(*, category_name: str) -> MessageCopy:
    return MessageCopy("カテゴリを更新しました", f"カテゴリ `{category_name}` を更新しました。")


def role_edit_prompt(*, category_name: str) -> MessageCopy:
    return MessageCopy("ロールを編集", f"`{category_name}` に表示するロールを選択してください。")


def boost_requirement_updated(*, category_name: str, required: bool) -> MessageCopy:
    status = "有効" if required else "無効"
    return MessageCopy(
        "ブースター限定設定を更新しました",
        f"`{category_name}` のブースター限定設定を {status} にしました。",
    )


def refresh_result(*, refreshed: bool) -> MessageCopy:
    if refreshed:
        return MessageCopy("ロールパネルを再描画しました", "ロールパネルを再描画しました。")
    return MessageCopy("ロールパネルを再描画できませんでした", "ロールパネルを再描画できませんでした。")


def admin_role_update(*, role_count: int, rejected_role_mentions: list[str]) -> str:
    message = f"カテゴリのロールを `{role_count}` 件に更新しました。"
    if rejected_role_mentions:
        message += "\n次のロールはBOTから操作できないため除外しました: " + ", ".join(rejected_role_mentions)
    return message


def role_select_modal_title(*, category_name: str) -> str:
    return f"{category_name[:35]} のロール選択"


def category_panel_content(*, category_name: str, description: str, requires_boost: bool) -> str:
    if requires_boost:
        description = f"{description}\n\n{BOOST_REQUIRED_NOTE}"
    return f"### {category_name}\n{description}"


def category_limit_notice(*, category_limit: int) -> str:
    return f"-# 表示対象は先頭{category_limit}カテゴリです。"


def panel_category_limit_notice(*, category_limit: int) -> str:
    return f"表示対象は先頭{category_limit}カテゴリです。"


def category_settings_title(*, page_index: int, total_pages: int) -> str:
    if total_pages <= 1:
        return CATEGORY_SETTINGS_TITLE
    return f"{CATEGORY_SETTINGS_TITLE} ({page_index}/{total_pages})"


def category_settings_value(*, display_order: int, description: str) -> str:
    return CATEGORY_SETTINGS_PREFIX.format(display_order=display_order) + description


def role_sync_result(
    *,
    added_role_mentions: list[str],
    removed_role_mentions: list[str],
    has_unmanageable_roles: bool,
) -> str:
    messages = [ROLE_SYNCED]
    if added_role_mentions:
        messages.append("追加: " + ", ".join(added_role_mentions))
    if removed_role_mentions:
        messages.append("削除: " + ", ".join(removed_role_mentions))
    if has_unmanageable_roles:
        messages.append(SYNC_UNMANAGEABLE_ROLE)
    return "\n".join(messages)

from __future__ import annotations

NONE = "なし"
GROUP_DESCRIPTION = "自分の通話を設定するコマンド"
UI_DESCRIPTION = "VCのコントローラーUIを表示"
NAME_DESCRIPTION = "VCの名前を変更"
LIMIT_DESCRIPTION = "VCに人数制限を設定"
BLOCK_DESCRIPTION = "VCからユーザーをブロック"
UNBLOCK_DESCRIPTION = "VCからブロックしたユーザーをブロック解除"
OP_DESCRIPTION = "VCの管理権限を別のユーザーにも付与"
DEOP_DESCRIPTION = "VCの管理権限を他のユーザーから剥奪"
PRIVATE_DESCRIPTION = "VCを非公開に設定"
PUBLIC_DESCRIPTION = "VCを公開に設定"
VC_NAME_LABEL = "vc名"
LIMIT_LABEL = "人数制限"
USER_LABEL = "ユーザー"
NEW_VC_NAME_DESCRIPTION = "新しく設定するVCの名前"
BLOCK_USER_DESCRIPTION = "VCに接続できなくするユーザー"
UNBLOCK_USER_DESCRIPTION = "VCブロックを解除するユーザー"
OP_USER_DESCRIPTION = "VCの管理権限を与えるユーザー"
DEOP_USER_DESCRIPTION = "管理権限を剥奪するユーザー"
UI_SENT = "VCのコントローラーUIを送信しました。"
NAME_CHANGE_RATE_LIMIT_ACTION = "VC名を変更できませんでした。"
PRIVATE_COMPLETED = "VCを非公開に設定しました。\n管理権限を与えることで他のユーザーがこのVCを見えるようになります。"
PUBLIC_COMPLETED = "VCを公開に設定しました。"
TEXT_CHANNEL_REQUIRED = "このコマンドはVCチャンネルでのみ使えます。"
CREATE_CHANNEL_REJECTED = "VC作成用チャンネル自体は操作できません。"
MANAGE_PERMISSION_REQUIRED = "VCの管理権限がありません。"
NAME_MODAL_TITLE = "VC名変更"
NEW_NAME_INPUT_LABEL = "新しいVCの名前"
NAME_CHANGE_COOLDOWN_LABEL = "VC名変更クールダウン中"
NAME_CHANGE_LABEL = "VC名を変更"
MAKE_PUBLIC_LABEL = "公開にする"
MAKE_PRIVATE_LABEL = "非公開にする"
UNLIMITED_LABEL = "無制限"
LIMIT_PLACEHOLDER = "人数制限"
BLOCK_PLACEHOLDER = "VCからブロックするユーザー"
BLOCKED_TITLE = "ユーザーをブロックしました。"
OP_PLACEHOLDER = "管理権限を与えるユーザー"
OPPED_TITLE = "ユーザーに管理権限を与えました。"
CONTROL_FALLBACK_TITLE = "VCコントロール"
LIMIT_SECTION_TITLE = "### 人数制限"
BLOCK_SECTION_TITLE = "### ブロックしたユーザー"
OP_SECTION_TITLE = "### 管理権限を与えたユーザー"


def vc_name_changed(*, vc_name: str) -> str:
    return f"VCの名前を`{vc_name}`に変更しました。"


def vc_limit_changed(*, limit: int) -> str:
    return f"チャンネルの人数制限を`{limit}`人に設定しました。"


def user_blocked(*, display_name: str) -> str:
    return f"`{display_name}`をブロックしました！"


def user_unblocked(*, display_name: str) -> str:
    return f"`{display_name}`をブロック解除しました！"


def user_opped(*, display_name: str) -> str:
    return f"`{display_name}`にVCの管理権限を与えました！"


def user_deopped(*, display_name: str) -> str:
    return f"`{display_name}`からVCの管理権限を剥奪しました！"


def modal_name_changed(*, actor_display_name: str, vc_name: str) -> str:
    return f"`{actor_display_name}`がVCの名前を`{vc_name}`に変更しました。"


def modal_limit_changed(*, actor_display_name: str, limit: int) -> str:
    return f"`{actor_display_name}`がVCの人数制限を`{limit}`に変更しました。"


def block_result(*, blocked_mentions: str, unblocked_mentions: str) -> str:
    return f"ブロックしたユーザー:\n{blocked_mentions}\n\nブロックを解除したユーザー:\n{unblocked_mentions}"


def op_result(*, opped_mentions: str, deopped_mentions: str) -> str:
    return f"管理権限を与えたユーザー:\n{opped_mentions}\n\n管理権限を剥奪したユーザー:\n{deopped_mentions}"


def default_channel_name(*, member_display_name: str) -> str:
    return f"{member_display_name}のVC"

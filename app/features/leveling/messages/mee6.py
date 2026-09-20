from __future__ import annotations

TRANSFER_DESCRIPTION = "MEE6から移行する"
SYNC_ROLE_LABEL = "ロール同期"
PRESTIGE_ANNOUNCE_LABEL = "プレステージ通知"
SYNC_ROLE_DESCRIPTION = "グレード・プレステージロールを同期するか"
PRESTIGE_ANNOUNCE_DESCRIPTION = "プレステージアナウンスを行うか"
FETCHING_MEE6 = "データ取得中..."
GUILD_EXECUTION_REQUIRED = "サーバー内でのみ実行できます。"
MEE6_FETCH_FAILED = "MEE6からのデータ取得に失敗しました"


def registration_progress(*, sync_role: bool, prestige_announce: bool) -> str:
    message = "データ取得完了、データベースに登録しています..."
    if sync_role:
        message += "\nロールの同期が有効です、通常より時間がかかります..."
    if prestige_announce:
        message += "\nプレステージアナウンスが有効です、通常より時間がかかります..."
    return message


def completed(*, sync_role: bool, prestige_announce: bool) -> str:
    message = "移行が完了しました"
    if sync_role:
        message += "\nロールの同期を行いました"
    if prestige_announce:
        message += "\nプレステージアナウンスを行いました"
    return message

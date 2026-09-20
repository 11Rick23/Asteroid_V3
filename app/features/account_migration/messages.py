from __future__ import annotations

from app.database.account_migration import AccountState, MigrationOptions, merge_leveling

from .discord_state import DiscordState, PermissionPair, to_overwrite

COMMAND_DESCRIPTION = "アカウントのデータ移行をプレビューし、確定後に実行します"
SOURCE_LABEL = "移行元"
TARGET_LABEL = "移行先"
LEVELING_LABEL = "レベリング"
ROLES_LABEL = "ロール"
BIRTHDAY_LABEL = "誕生日"
FC_LABEL = "フリカテ権限"
SOURCE_DESCRIPTION = "データを移動する元のアカウント（退会済みアカウントもIDで指定できます）"
TARGET_DESCRIPTION = "移行先のサーバーメンバー"
LEVELING_DESCRIPTION = "シャード・パワー・未受取XPを合算して移動します（初期値: True）"
ROLES_DESCRIPTION = "移行元の操作可能なロールを移行先へ追加し、移行元から外します（初期値: True）"
BIRTHDAY_DESCRIPTION = "移行先の誕生日を移行元の値で上書きし、移行元から削除します（初期値: True）"
FC_DESCRIPTION = "フリカテの個別権限を移行元の設定で上書きし、移行元から削除します（初期値: True）"
CONFIRM = "確定して移行"
CANCEL = "キャンセル"
PREVIEW_TITLE = "アカウント移行の確認"
PREVIEW_NOTE = (
    "選択したデータを移動し、移行元から削除します。\n"
    "誕生日・フリカテ個別権限は、移行元が未設定なら移行先の設定を削除します。\n"
    "ロールと権限の詳細は添付ファイルをご確認ください。\n"
    "このチャンネルに移行記録と復元コマンドを残します。確認の有効期限は5分です。"
)
UNAUTHORIZED = "この確認はコマンドを実行した管理者だけが操作できます。"
USED = "この確認は実行済み、または処理中です。"
CANCELLED = "移行をキャンセルしました。"
COMPLETED = "移行が完了しました。このチャンネルに移行記録と復元コマンドを保存しました。"
RECORD_FAILED = (
    "移行は完了しましたが、記録の完了表示を更新できませんでした。移行前に保存した復元記録をご確認ください。"
)
FAILED = "移行に失敗しました。DBの変更とDiscordの変更を巻き戻しました。"
ROLLBACK_FAILED = "移行に失敗し、一部の変更を巻き戻せませんでした。記録を確認して手動で復元してください。"
COMMIT_UNCERTAIN = "DBの確定結果を確認できませんでした。二重移行を避けるため、記録と現在のデータを確認してください。"
ERRORS = {
    "accounts": "移行元と移行先は別の人間のアカウントを指定し、移行先はサーバーに参加している必要があります。",
    "roles": "Botが移行元のロールを操作できません。Botの管理権限とロールの上下関係を確認してください。",
    "permissions": "Botに対象フリカテの権限を編集する権限がありません。",
    "stale": "プレビュー後にデータが変更されました。コマンドを再実行して内容を確認してください。",
    "empty": "移行元に選択した種類のデータがありません。",
    "disabled": "移行対象を1つ以上有効にしてください。",
    "leveling_disabled": "レベリングの移行にはレベリング機能を有効にしてください（復元用コマンドが必要です）。",
    "channel": "記録を送信できるサーバーのテキストチャンネルで実行してください。",
}
RANGE_ERROR = "合算後の数量が保存上限を超えるため、移行できません。"


def birthday(value: AccountState) -> str:
    return value.birthday.strftime("%m/%d") if value.birthday else "未設定"


def preview(source: AccountState, target: AccountState, options: MigrationOptions, state: DiscordState) -> str:
    lines = [f"<@{source.user_id}> → <@{target.user_id}>", PREVIEW_NOTE]
    if options.leveling:
        shards, powers, pending = merge_leveling(source, target)
        lines.extend(
            [
                "シャード（テキスト/ボイス/ボーナス）: "
                f"{target.shards.text}/{target.shards.voice}/{target.shards.bonus}"
                f" → {shards.text}/{shards.voice}/{shards.bonus}",
                "パワー（テキスト/ボイス/アクション）: "
                f"{target.powers.text}/{target.powers.voice}/{target.powers.action}"
                f" → {powers.text}/{powers.voice}/{powers.action}",
                f"未受取XP（ボイスシャード/ボーナス/パワー）: "
                f"{target.pending.voice_shard}/{target.pending.bonus_shard}/{target.pending.voice_power}"
                f" → {pending.voice_shard}/{pending.bonus_shard}/{pending.voice_power}",
                "獲得履歴も移動します。移行元の数量は0になります。",
            ]
        )
    else:
        lines.append("レベリング: 移行しない")
    lines.append(
        f"ロール: {len(state.transferable_roles)}件を引き継ぎ、{len(state.skipped_roles)}件を対象外"
        if options.roles
        else "ロール: 移行しない"
    )
    lines.append(
        f"誕生日: {birthday(target)} → {birthday(source)}（移行元は未設定に変更）"
        if options.birthday
        else "誕生日: 移行しない"
    )
    lines.append(
        f"フリカテ個別権限: {len(state.permissions)}チャンネルを上書き"
        if options.free_category
        else "フリカテ権限: 移行しない"
    )
    return "\n\n".join(lines)


def permission_text(value: PermissionPair) -> str:
    overwrite = to_overwrite(value)
    if overwrite is None:
        return "個別設定なし"
    allow, deny = overwrite.pair()
    return (
        f"許可: {', '.join(name for name, enabled in allow if enabled) or 'なし'}; "
        f"拒否: {', '.join(name for name, enabled in deny if enabled) or 'なし'}"
    )


def details(source: AccountState, target: AccountState, state: DiscordState, options: MigrationOptions) -> str:
    lines = [preview(source, target, options, state)]
    if options.leveling:
        lines += ["", "移行前の数量（復元コマンド）", restore_commands(source), restore_commands(target)]
    if options.roles:
        lines += [
            f"移行元ロールID: {state.source_roles}",
            f"移行先ロールID: {state.target_roles}",
            f"移動するロールID: {state.transferable_roles}",
            f"対象外（連携管理・削除済み）ロールID: {state.skipped_roles}",
        ]
    for item in state.permissions:
        lines += [
            f"チャンネル {item.channel_id}",
            f"  移行元: {permission_text(item.source)} → 個別設定なし",
            f"  移行先: {permission_text(item.target)} → {permission_text(item.source)}",
        ]
    return "\n".join(lines)


def restore_commands(state: AccountState) -> str:
    prefix = f"ユーザー:{state.user_id}"
    return (
        f"/leveling shard set {prefix} テキスト:{state.shards.text} ボイス:{state.shards.voice} "
        f"ボーナス:{state.shards.bonus}\n"
        f"/leveling power set {prefix} テキスト:{state.powers.text} ボイス:{state.powers.voice} "
        f"アクション:{state.powers.action}\n"
        f"/leveling pending set {prefix} ボイスシャード:{state.pending.voice_shard} "
        f"ボーナスシャード:{state.pending.bonus_shard} ボイスパワー:{state.pending.voice_power} "
        f"半分通知:{str(state.pending.half_notify).lower()} 上限通知:{str(state.pending.full_notify).lower()}"
    )


def record(source: AccountState, target: AccountState, actor_id: int, options: MigrationOptions, status: str) -> str:
    text = f"アカウント移行: {source.user_id} → {target.user_id}\n実行者: {actor_id}\n状態: {status}"
    if options.leveling:
        text += (
            "\n移行直前の数量に戻すコマンド（両アカウントで全て実行）:\n```\n"
            f"{restore_commands(source)}\n{restore_commands(target)}\n```\n"
            "復元は実行時点の数量を上書きします。獲得履歴・ロール・誕生日・フリカテ権限はsetでは復元されません。"
        )
    return text

from __future__ import annotations

from app.database.account_migration import AccountState, MigrationOptions, merge_leveling

from .discord_state import DiscordState, PermissionPair, to_overwrite

COMMAND_DESCRIPTION = "アカウントのデータを確認して移行します"
SOURCE_LABEL = "移行元"
TARGET_LABEL = "移行先"
LEVELING_LABEL = "レベリング"
ROLES_LABEL = "ロール"
BIRTHDAY_LABEL = "誕生日"
FC_LABEL = "フリカテ権限"
SOURCE_DESCRIPTION = "移行元アカウント（退会済みの場合はID指定）"
TARGET_DESCRIPTION = "移行先のサーバーメンバー"
LEVELING_DESCRIPTION = "シャード・パワー・未受取XPを合算して移動（初期値: True）"
ROLES_DESCRIPTION = "操作可能なロールを移動（初期値: True）"
BIRTHDAY_DESCRIPTION = "誕生日を移行元の値で上書きして移動（初期値: True）"
FC_DESCRIPTION = "フリカテ個別権限を移行元の設定で上書きして移動（初期値: True）"
CONFIRM = "確定して移行"
CANCEL = "キャンセル"
PREVIEW_TITLE = "アカウント移行の確認"
PREVIEW_NOTE = (
    "対象データは移行元から削除（除外ロールは保持）。\n誕生日・個別権限は未設定も上書き。詳細は添付／確認期限5分。"
)
UNAUTHORIZED = "操作できるのは実行した管理者だけです。"
USED = "処理中または実行済みです。"
CANCELLED = "移行をキャンセルしました。"
COMPLETED = "移行が完了しました。"
RECORD_FAILED = "移行済みですが、完了記録の更新に失敗しました。保存済みの記録をご確認ください。"
FAILED = "移行に失敗しました。変更は巻き戻しました。"
ROLLBACK_FAILED = "移行に失敗し、一部を復元できませんでした。記録を確認して手動で復元してください。"
COMMIT_UNCERTAIN = "DBの確定結果が不明です。再実行前に記録と現在のデータをご確認ください。"
ERRORS = {
    "accounts": "移行元と移行先は別の人間のアカウントを指定し、移行先はサーバーに参加している必要があります。",
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
    lines = [f"<@{source.user_id}> → <@{target.user_id}>", "", "移行先の変更"]
    if options.leveling:
        shards, powers, pending = merge_leveling(source, target)
        lines.extend(
            [
                f"シャード: {target.shards.total:,} → {shards.total:,}",
                f"パワー: {target.powers.text + target.powers.voice + target.powers.action:,}"
                f" → {powers.text + powers.voice + powers.action:,}",
                f"未受取XP: シャード {target.pending.voice_shard + target.pending.bonus_shard:,}"
                f" → {pending.voice_shard + pending.bonus_shard:,}"
                f"／パワー {target.pending.voice_power:,} → {pending.voice_power:,}",
            ]
        )
    else:
        lines.append("レベリング: 移行しない")
    lines.append(
        f"ロール: {len(state.transferable_roles)}件を引き継ぎ、{len(state.skipped_roles)}件を対象外"
        if options.roles
        else "ロール: 移行しない"
    )
    if options.roles and state.skipped_roles:
        excluded = "、".join(f"<@&{role_id}>" for role_id in state.skipped_roles[:5])
        if len(state.skipped_roles) > 5:
            excluded += f" ほか{len(state.skipped_roles) - 5}件（添付参照）"
        lines.append(f"除外するロール: {excluded}")
    lines.append(f"誕生日: {birthday(target)} → {birthday(source)}" if options.birthday else "誕生日: 移行しない")
    lines.append(
        f"フリカテ個別権限: {len(state.permissions)}チャンネルを上書き"
        if options.free_category
        else "フリカテ権限: 移行しない"
    )
    return "\n".join([*lines, "", PREVIEW_NOTE])


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
        shards, powers, pending = merge_leveling(source, target)
        lines += [
            "",
            "移行先の移行後の内訳",
            f"シャード（テキスト/ボイス/ボーナス）: {shards.text}/{shards.voice}/{shards.bonus}",
            f"パワー（テキスト/ボイス/アクション）: {powers.text}/{powers.voice}/{powers.action}",
            f"未受取XP（ボイスシャード/ボーナスシャード/ボイスパワー）: "
            f"{pending.voice_shard}/{pending.bonus_shard}/{pending.voice_power}",
        ]
        lines += ["", "移行前の数量（復元コマンド）", restore_commands(source), restore_commands(target)]
    if options.roles:
        lines += [
            f"移行元ロールID: {state.source_roles}",
            f"移行先ロールID: {state.target_roles}",
            f"移動するロールID: {state.transferable_roles}",
            f"対象外（権限不足・Bot以上のロール・連携管理・削除済み）ロールID: {state.skipped_roles}",
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
            "\n数量の復元（両アカウントで実行）:\n```\n"
            f"{restore_commands(source)}\n{restore_commands(target)}\n```\n"
            "数量を移行前の値で上書きします。履歴・ロール・誕生日・権限は復元対象外です。"
        )
    return text

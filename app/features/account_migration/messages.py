from __future__ import annotations

from collections.abc import Mapping

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
ROLES_DESCRIPTION = "操作可能なロールを移動。共通ロールは移行元にも保持（初期値: True）"
BIRTHDAY_DESCRIPTION = "設定済みの誕生日を移動。競合時は移行元を優先（初期値: True）"
FC_DESCRIPTION = "設定済みのフリカテ個別権限を移動。競合時は移行元を優先（初期値: True）"
CONFIRM = "確定して移行"
CANCEL = "キャンセル"
PREVIEW_TITLE = "🔄 アカウント移行"
CHECKING = "🔎 移行前チェック中"
CHECK_READY = "🔎 移行前チェック"
PREVIEW_FOOTER = "📎 内訳・除外一覧は添付ファイルへ ｜ 確認期限 5分"
PREVIEW_NOTE = (
    "対象データは移行元から削除。共通・除外ロールは保持。\n"
    "誕生日・個別権限は**未設定なら移行先を保持、競合時は移行元を優先**します。"
)
UNAUTHORIZED = "操作できるのは実行した管理者だけです。"
USED = "処理中または実行済みです。"
CANCELLED = "🚫 移行をキャンセルしました。"
COMPLETED = "✅ 移行が完了しました。"
PROCESSING = "⏳ 移行しています…"
STOPPED = "⏹️ 処理を終了しました。"
RESTORE_TITLE = "↩️ レベル復元用のコマンド"
RESTORE_NOTE = "数量を移行前の値で上書きします。履歴・ロール・誕生日・権限は復元対象外です。"
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


def preview_fields(
    source: AccountState, target: AccountState, options: MigrationOptions, state: DiscordState
) -> list[tuple[str, str, bool]]:
    fields: list[tuple[str, str, bool]] = []
    if options.leveling:
        shards, powers, pending = merge_leveling(source, target)
        fields.extend(
            [
                ("💎 シャード", f"{target.shards.total:,} → **{shards.total:,}**", True),
                (
                    "⚡ パワー",
                    f"{target.powers.text + target.powers.voice + target.powers.action:,}"
                    f" → **{powers.text + powers.voice + powers.action:,}**",
                    True,
                ),
                (
                    "🎙️ 未受取XP",
                    f"シャード {target.pending.voice_shard + target.pending.bonus_shard:,}"
                    f" → **{pending.voice_shard + pending.bonus_shard:,}**\n"
                    f"パワー {target.pending.voice_power:,} → **{pending.voice_power:,}**",
                    False,
                ),
            ]
        )
    else:
        fields.append(("💎 レベリング", "移行しない", False))
    fields += [
        (
            "🏷️ ロール",
            f"**{len(state.moving_roles)}件**を移動\n共通 **{len(state.shared_roles)}件**は移行元にも保持"
            if options.roles
            else "移行しない",
            True,
        ),
        (
            "🎂 誕生日",
            (
                f"{birthday(target)} → **{birthday(source)}**"
                if source.birthday is not None
                else f"{birthday(target)}（変更なし）"
            )
            if options.birthday
            else "移行しない",
            True,
        ),
        (
            "🔑 フリカテ権限",
            f"**{len(state.permissions)}件**を引き継ぎ" if options.free_category else "移行しない",
            False,
        ),
    ]
    if options.roles and state.skipped_roles:
        excluded = " ".join(f"<@&{role_id}>" for role_id in state.skipped_roles[:5])
        if len(state.skipped_roles) > 5:
            excluded += f"\nほか{len(state.skipped_roles) - 5}件（添付参照）"
        fields.append((f"⏭️ 除外ロール · {len(state.skipped_roles)}件", excluded, False))
    fields.append(("⚠️ 確認事項", PREVIEW_NOTE, False))
    return fields


def permission_text(value: PermissionPair) -> str:
    overwrite = to_overwrite(value)
    if overwrite is None:
        return "個別設定なし"
    allow, deny = overwrite.pair()
    return (
        f"許可: {', '.join(name for name, enabled in allow if enabled) or 'なし'}; "
        f"拒否: {', '.join(name for name, enabled in deny if enabled) or 'なし'}"
    )


def plain_identity(user_id: int, names: Mapping[int, str]) -> str:
    name = names.get(user_id)
    return f"{name} (ID: {user_id})" if name else f"ID: {user_id}"


def details(
    source: AccountState,
    target: AccountState,
    state: DiscordState,
    options: MigrationOptions,
    names: Mapping[int, str] | None = None,
) -> str:
    names = names or {}
    enabled = [
        label
        for label, selected in (
            (LEVELING_LABEL, options.leveling),
            (ROLES_LABEL, options.roles),
            (BIRTHDAY_LABEL, options.birthday),
            (FC_LABEL, options.free_category),
        )
        if selected
    ]
    lines = [
        "アカウント移行",
        "",
        f"移行元: {plain_identity(source.user_id, names)}",
        f"移行先: {plain_identity(target.user_id, names)}",
        f"移行対象: {'、'.join(enabled)}",
        "対象データは移行元から削除します。共通・除外ロールは保持します。",
    ]
    if options.leveling:
        shards, powers, pending = merge_leveling(source, target)
        lines += [
            "",
            "[移行先の移行後の内訳]",
            f"シャード（テキスト/ボイス/ボーナス）: {shards.text}/{shards.voice}/{shards.bonus}",
            f"パワー（テキスト/ボイス/アクション）: {powers.text}/{powers.voice}/{powers.action}",
            f"未受取XP（ボイスシャード/ボーナスシャード/ボイスパワー）: "
            f"{pending.voice_shard}/{pending.bonus_shard}/{pending.voice_power}",
        ]
        lines += ["獲得履歴も移行先へ移動します。"]
    if options.birthday:
        lines += [
            "",
            "[誕生日]",
            f"移行元: {birthday(source)} → 未設定",
            f"移行先: {birthday(target)} → {birthday(source if source.birthday is not None else target)}",
        ]
    if options.roles:
        for title, role_ids in (
            ("移行元のロール（移行前）", state.source_roles),
            ("移行先のロール（移行前）", state.target_roles),
            ("移動するロール", state.moving_roles),
            ("共通ロール（移行元にも保持）", state.shared_roles),
            ("除外ロール（移行元に保持）", state.skipped_roles),
        ):
            lines += ["", f"[{title}]"]
            lines += [f"  {plain_identity(role_id, names)}" for role_id in role_ids] or ["  なし"]
    if options.free_category:
        lines += ["", "[フリカテ個別権限]", "移行元で設定済みの項目を優先し、未設定の項目は移行先の設定を保持します。"]
        if not state.permissions:
            lines.append("対象チャンネルなし")
    for item in state.permissions:
        lines += [
            f"チャンネル: {plain_identity(item.channel_id, names)}",
            f"  移行元: {permission_text(item.source)} → 個別設定なし",
            f"  移行先: {permission_text(item.target)} → {permission_text(item.migrated)}",
        ]
    if options.leveling:
        lines += [
            "",
            "[レベル復元用のコマンド]",
            "両アカウントの数量を移行前の値で上書きします。",
            "履歴・ロール・誕生日・権限は復元対象外です。",
            "",
            "移行元:",
            restore_commands(source),
            "",
            "移行先:",
            restore_commands(target),
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


def status_accounts(source_id: int, target_id: int, actor_id: int) -> str:
    return f"<@{source_id}> → <@{target_id}>\n実行者: <@{actor_id}>"


def status_summary(
    source: AccountState, target: AccountState, options: MigrationOptions, state: DiscordState, *, completed: bool
) -> str:
    title = "移行先の変更" if completed else "移行予定"
    fields = preview_fields(source, target, options, state)[:-1]
    return f"### {title}\n" + "\n\n".join(f"**{name}**\n{value}" for name, value, _ in fields)


def restore_block(state: AccountState, *, source: bool) -> str:
    label = SOURCE_LABEL if source else TARGET_LABEL
    return f"**{label}** <@{state.user_id}>\n```\n{restore_commands(state)}\n```"

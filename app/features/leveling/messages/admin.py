from __future__ import annotations

from app.common.constants import AsteroidEmoji

ADMIN_GROUP_DESCRIPTION = "管理者用レベリングシステム関連コマンド"
BOOSTER_GROUP_DESCRIPTION = "ブースター設定"
ADMIN_SHARD_GROUP_DESCRIPTION = "シャード管理"
ADMIN_POWER_GROUP_DESCRIPTION = "パワー管理"
TEXT_LABEL = "テキスト"
VOICE_LABEL = "ボイス"
BONUS_LABEL = "ボーナス"
ACTION_LABEL = "アクション"
ROLE_LABEL = "ロール"
NAME_LABEL = "名前"
AMOUNT_LABEL = "数量"
MULTIPLIER_LABEL = "倍率"
SHARD_TYPE_LABEL = "シャード種類"
POWER_TYPE_LABEL = "パワー種類"
DELETE_DATA_LABEL = "データを削除"
ACTION_POWER_TOTAL_DESCRIPTION = "現在の合計アクションパワーを確認します"
BOOSTER_ADD_DESCRIPTION = "経験値ブースターを追加します"
BOOSTER_DELETE_DESCRIPTION = "経験値ブースターを削除します"
SHARD_ADD_DESCRIPTION = "ユーザーにシャードを追加します"
SHARD_REMOVE_DESCRIPTION = "ユーザーからシャードを減らします"
POWER_ADD_DESCRIPTION = "ユーザーにパワーを追加します"
POWER_REMOVE_DESCRIPTION = "ユーザーからパワーを減らします"
AGGREGATE_DESCRIPTION = "現在のデータで月間ランキングを集計します"
AGGREGATE_DELETE_DESCRIPTION = "集計後に月間パワーデータを削除するか"
BOOSTER_ADDED = "経験値ブースターを追加しました。"
BOOSTER_DELETED = "経験値ブースターを削除しました。"
AGGREGATE_FAILED = "月間ランキングを集計できませんでした。"


def action_power_total(*, total_action_power: int) -> str:
    return f"蓄積アクションパワー: {AsteroidEmoji.ACTION_POWER} {total_action_power}"


def shard_added(*, user_mention: str, amount: str, shard_type: str, grade_up_amount: int, prestige_amount: int) -> str:
    return (
        f"{user_mention}に`{amount}`{shard_type}シャードを付与しました\n"
        f"{grade_up_amount}回グレードアップしました、{prestige_amount}回プレステージしました"
    )


def shard_removed(*, user_mention: str, amount: str, shard_type: str) -> str:
    return f"{user_mention}から`{amount}`{shard_type}シャードを減らしました"


def aggregate_result(*, ranked_count: int, delete_data: bool) -> str:
    delete_status = "実行済み" if delete_data else "未実行"
    return f"現在のデータで月間ランキングを集計しました。対象者: {ranked_count}人\n集計後のデータ削除: {delete_status}"

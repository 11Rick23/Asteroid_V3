from __future__ import annotations

from app.common.constants import AsteroidEmoji

VOICE_XP_BUTTON_LABEL = "VC経験値を獲得する"
VOICE_XP_NOT_EARNED = "VC経験値を獲得していません"
VOICE_XP_PANEL_TITLE = "VC経験値獲得はこちら"
VOICE_XP_PANEL_DESCRIPTION = "ボタンを押すとVC経験値を獲得します"
VOICE_XP_LIMIT_TITLE = "VC経験値獲得上限到達！"
SETUP_VOICE_XP_DESCRIPTION = "VC経験値獲得用のボタンを設置します"
CHANNEL_NOT_MESSAGEABLE = "このチャンネルには送信できません。"
VOICE_XP_BUTTON_INSTALLED = "VC経験値獲得用のボタンを設置しました！"
MONTHLY_RANKING_NO_DATA = "ランキングデータはありません。"
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
USER_LABEL = "ユーザー"
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
RANKING_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、ランキングは現在確認できません。時間を空けてもう一度ご確認ください。"
)
POWER_RANKING_TITLE = "パワーランキング"
SHARD_RANKING_TITLE = "シャードランキング"
HOTNESS_RANKING_TITLE = "🔥 急上昇ランキング"
POWER_GROUP_DESCRIPTION = "月間ランキング系コマンド"
POWER_TOP_DESCRIPTION = "現在のパワーランキングを表示します"
SHARD_GROUP_DESCRIPTION = "恒常ランキング系コマンド"
REWARD_GROUP_DESCRIPTION = "グレード・プレステージ報酬関連のコマンド"
SHARD_TOP_DESCRIPTION = "現在の恒常ランキングを表示します"
CURRENT_SHARD_RANKING_HEADING = "現在のシャードランキングを表示します"
XP_BOOST_DESCRIPTION = "現在開催中のXPブーストを表示します"
NO_XP_BOOST = "現在開催中のXPブーストはありません"
ROLE_NOT_FOUND = "ロールが見つかりません"
UNLIMITED = "無期限"
GRADE_REWARD_DESCRIPTION = "グレードに応じたロール報酬を表示します"
PRESTIGE_REWARD_DESCRIPTION = "プレステージに応じたロール報酬を表示します"
NO_REWARD_ROLES = "報酬ロールは設定されていません。"
CLAIM_DESCRIPTION = "VC経験値を獲得します"
RANK_DESCRIPTION = "自分の順位を表示します"
RANK_USER_DESCRIPTION = "順位を表示するユーザー"
TRANSFER_DESCRIPTION = "MEE6から移行する"
SYNC_ROLE_LABEL = "ロール同期"
PRESTIGE_ANNOUNCE_LABEL = "プレステージ通知"
SYNC_ROLE_DESCRIPTION = "グレード・プレステージロールを同期するか"
PRESTIGE_ANNOUNCE_DESCRIPTION = "プレステージアナウンスを行うか"
FETCHING_MEE6 = "データ取得中..."
GUILD_EXECUTION_REQUIRED = "サーバー内でのみ実行できます。"
MEE6_FETCH_FAILED = "MEE6からのデータ取得に失敗しました"
LEVEL_UP_TITLE = "レベルアップ！"
PRESTIGE_UP_TITLE = "プレステージ！"
PRESTIGE_ACHIEVEMENT_TITLE = "プレステージ達成！"
RANKING_NO_DATA = "ランキングデータはありません。"
PREVIOUS_PAGE_LABEL = "<"
NEXT_PAGE_LABEL = ">"


def action_power_total(*, total_action_power: int) -> str:
    return f"蓄積アクションパワー: {AsteroidEmoji.ACTION_POWER} {total_action_power}"


def voice_xp_limit(*, member_mention: str) -> str:
    return (
        f"**{member_mention}さんはVC経験値獲得上限に到達しました！\n"
        "VC経験値を更に獲得するには`経験値を獲得する`ボタンを押すか、"
        "`/claim_voice_xp` コマンドを実行してください！**"
    )


def monthly_ranking_announcement(*, ranking_text: str) -> str:
    return (
        "# ということで、今回のtop10は...\n\n"
        f"{ranking_text or MONTHLY_RANKING_NO_DATA}\n"
        "# このようになりました！おめでとうございます！"
    )


def monthly_ranking_line(*, ranking: int, user_id: int) -> str:
    return f"> ### {ranking}位: <@{user_id}>"


def monthly_power_ranking_heading(*, limit: int) -> str:
    return f"月間パワー 現在のTOP{limit}"


def cumulative_shard_ranking_heading(*, limit: int) -> str:
    return f"累計シャード 現在のTOP{limit}"


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


def voice_xp_claimed(*, user_mention: str, voice_shard: str, voice_power: str, bonus_shard: str) -> str:
    return (
        f"{user_mention} ボイスシャードを`{voice_shard}`獲得しました\n"
        f"ボイスパワーを`{voice_power}`獲得しました\n"
        f"ボイスボーナスシャードを`{bonus_shard}`獲得しました"
    )


def power_ranking_description(*, heading: str, trailing: str = "") -> str:
    return (
        f"{heading}\n\n"
        f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
        f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
        f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
        f"{trailing}"
    )


def shard_ranking_description(*, heading: str, trailing: str = "") -> str:
    return (
        f"{heading}\n\n"
        f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
        f"{AsteroidEmoji.GRADE}: グレード\n"
        f"{AsteroidEmoji.SHARD}: シャード\n"
        f"{trailing}"
    )


def hotness_ranking_description(*, limit: int) -> str:
    return f"直近24時間の経験値獲得量 TOP{limit}"


def xp_boost_entry(*, name: str, role_mention: str, boost_amount: int, end_time: str) -> str:
    return f"### {name}\n対象ロール: {role_mention}\nブースト量: {boost_amount}%\nブースト終了時間: {end_time}"


def xp_boost_list(*, entries: list[str]) -> str:
    return (
        "# 開催中のXPブースト一覧\n"
        "現在開催中のXPブーストです\n"
        "XPブーストはシャードのみに適用されます、パワーには全く影響がありませんのでご注意ください\n\n"
        + "\n\n".join(entries)
    )


def grade_reward_entry(*, grade: int, role_mention: str) -> str:
    return f"### Grade. {grade}\n{role_mention}"


def prestige_reward_entry(*, prestige: int, role_mention: str) -> str:
    return f"### Prestige. {prestige}\n{role_mention}"


def grade_reward_list(*, entries: list[str]) -> str:
    return "# グレードロール報酬\nグレードに応じたロール報酬を表示します\n\n" + (
        "\n\n".join(entries) if entries else NO_REWARD_ROLES
    )


def prestige_reward_list(*, entries: list[str]) -> str:
    return "# プレステージロール報酬\nプレステージに応じたロール報酬を表示します\n\n" + (
        "\n\n".join(entries) if entries else NO_REWARD_ROLES
    )


def user_has_no_power(*, display_name: str) -> str:
    return f"{display_name}はまだパワーを獲得していません"


def user_has_no_shards(*, display_name: str) -> str:
    return f"{display_name}はまだシャードを獲得していません"


def mee6_registration_progress(*, sync_role: bool, prestige_announce: bool) -> str:
    message = "データ取得完了、データベースに登録しています..."
    if sync_role:
        message += "\nロールの同期が有効です、通常より時間がかかります..."
    if prestige_announce:
        message += "\nプレステージアナウンスが有効です、通常より時間がかかります..."
    return message


def mee6_completed(*, sync_role: bool, prestige_announce: bool) -> str:
    message = "移行が完了しました"
    if sync_role:
        message += "\nロールの同期を行いました"
    if prestige_announce:
        message += "\nプレステージアナウンスを行いました"
    return message


def grade_up(*, author_mention: str, old_grade: int, new_grade: int) -> str:
    return f"{author_mention}さんがGrade. {old_grade}からGrade. {new_grade}へグレードアップ！"


def prestige_up(*, author_mention: str, old_prestige: int, new_prestige: int) -> str:
    return f"{author_mention}さんがPrestige. {old_prestige}からPrestige. {new_prestige}へプレステージ！"


def prestige_achievement(*, member_mention: str, achievement: str) -> str:
    return f"{member_mention}さんが{achievement}を達成しました！\nおめでとうございます！"


def unknown_member(*, user_id: int) -> str:
    return f"不明なメンバー [{user_id}]"


def prestige_name(*, prestige: int) -> str:
    return f"プレステージ{prestige}"


def ranking_position(*, ranking: int) -> str:
    medals = ("🥇", "🥈", "🥉")
    return medals[ranking - 1] if 1 <= ranking <= len(medals) else f"{ranking}位"


def ranking_header(*, title: str, description: str) -> str:
    return f"# {title}\n{description}"


def star_grade_details(
    *,
    display_name: str,
    ranking: int | None,
    next_grade: int,
    grade_progress_bar: str,
    grade_progress: int,
    prestige: str,
    grade: int,
    shard: str,
    text_shard: str,
    voice_shard: str,
    bonus_shard: str,
) -> str:
    ranking_text = f"現在の順位: {ranking}位\n\n" if ranking is not None else ""
    return (
        f"# {display_name}のシャード\n"
        f"{ranking_text}"
        f"{AsteroidEmoji.GRADE}Grade. {next_grade}までの進捗ケージ\n"
        f"## {grade_progress_bar} {grade_progress}%\n\n"
        f"### プレステージ数\n{AsteroidEmoji.PRESTIGE} {prestige}\n"
        f"### グレード数\n{AsteroidEmoji.GRADE} {grade}\n"
        f"### シャード数\n{AsteroidEmoji.SHARD} {shard}\n"
        f"### 累計テキストシャード数\n{AsteroidEmoji.TEXT_SHARD} {text_shard}\n"
        f"### 累計ボイスシャード数\n{AsteroidEmoji.VOICE_SHARD} {voice_shard}\n"
        f"### 累計ボーナスシャード\n{AsteroidEmoji.BONUS_SHARD} {bonus_shard}"
    )


def shard_ranking_entry(
    *, ranking: str, display_name: str, prestige: str, grade: int, shard: str, total_shards: str
) -> str:
    return (
        f"### {ranking}: {display_name}\n"
        f"{AsteroidEmoji.PRESTIGE} {prestige}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.GRADE} {grade}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.SHARD} {shard}\n"
        f"合計: {total_shards}"
    )


def power_details(
    *, display_name: str, ranking: int | None, text_power: str, voice_power: str, action_power: str
) -> str:
    ranking_text = f"現在の順位: {ranking}位\n\n" if ranking is not None else ""
    return (
        f"# {display_name}のパワー\n"
        f"{ranking_text}"
        f"### テキストパワー数\n{AsteroidEmoji.TEXT_POWER} {text_power}\n"
        f"### ボイスパワー数\n{AsteroidEmoji.VOICE_POWER} {voice_power}\n"
        f"### アクションパワー数\n{AsteroidEmoji.ACTION_POWER} {action_power}"
    )


def power_ranking_entry(
    *, ranking: str, display_name: str, text_power: str, voice_power: str, action_power: str, total_power: str
) -> str:
    return (
        f"### {ranking}: {display_name}\n"
        f"{AsteroidEmoji.TEXT_POWER} {text_power}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_POWER} {voice_power}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.ACTION_POWER} {action_power}\n"
        f"合計: {total_power}"
    )


def hotness_ranking_entry(*, ranking: str, display_name: str, hotness: str) -> str:
    return f"### {ranking}: {display_name}\n🔥 合計: {hotness}"


def rank_card(
    *,
    display_name: str,
    grade_progress_bar: str,
    grade_progress: int,
    total_shards: str,
    shard_ranking: int,
    prestige: str,
    grade: int,
    shard: str,
    text_shard: str,
    voice_shard: str,
    bonus_shard: str,
    total_power: str,
    power_ranking: int,
    text_power: str,
    voice_power: str,
    action_power: str,
) -> str:
    return (
        f"# {display_name}のランクカード\n"
        f"次のグレードまで…\n## {grade_progress_bar} {grade_progress}%\n"
        f"### {total_shards}シャード - 現在{shard_ranking}位\n"
        f"{AsteroidEmoji.PRESTIGE} {prestige}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.GRADE} {grade}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.SHARD} {shard}\n"
        f"{AsteroidEmoji.TEXT_SHARD} {text_shard}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_SHARD} {voice_shard}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.BONUS_SHARD} {bonus_shard}\n\n"
        f"### {total_power}パワー - 現在{power_ranking}位\n"
        f"{AsteroidEmoji.TEXT_POWER} {text_power}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_POWER} {voice_power}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.ACTION_POWER} {action_power}"
    )

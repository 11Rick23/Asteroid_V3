from __future__ import annotations

from app.common.constants import AsteroidEmoji

from .common import RANKING_NO_DATA

RANKING_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、ランキングは現在確認できません。時間を空けてもう一度ご確認ください。"
)
POWER_RANKING_TITLE = "パワーランキング"
SHARD_RANKING_TITLE = "シャードランキング"
HOTNESS_RANKING_TITLE = "🔥 急上昇ランキング"
POWER_GROUP_DESCRIPTION = "月間ランキング系コマンド"
POWER_TOP_DESCRIPTION = "現在のパワーランキングを表示します"
SHARD_GROUP_DESCRIPTION = "恒常ランキング系コマンド"
SHARD_TOP_DESCRIPTION = "現在の恒常ランキングを表示します"
CURRENT_SHARD_RANKING_HEADING = "現在のシャードランキングを表示します"
RANK_DESCRIPTION = "自分の順位を表示します"
RANK_USER_DESCRIPTION = "順位を表示するユーザー"


def monthly_ranking_announcement(*, ranking_text: str) -> str:
    return (
        "# ということで、今回のtop10は...\n\n"
        f"{ranking_text or RANKING_NO_DATA}\n"
        "# このようになりました！おめでとうございます！"
    )


def monthly_ranking_line(*, ranking: int, user_id: int) -> str:
    return f"> ### {ranking}位: <@{user_id}>"


def monthly_power_ranking_heading(*, limit: int) -> str:
    return f"月間パワー 現在のTOP{limit}"


def cumulative_shard_ranking_heading(*, limit: int) -> str:
    return f"累計シャード 現在のTOP{limit}"


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


def user_has_no_power(*, display_name: str) -> str:
    return f"{display_name}はまだパワーを獲得していません"


def user_has_no_shards(*, display_name: str) -> str:
    return f"{display_name}はまだシャードを獲得していません"


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

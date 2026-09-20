from __future__ import annotations

REWARD_GROUP_DESCRIPTION = "グレード・プレステージ報酬関連のコマンド"
XP_BOOST_DESCRIPTION = "現在開催中のXPブーストを表示します"
NO_XP_BOOST = "現在開催中のXPブーストはありません"
UNLIMITED = "無期限"
GRADE_REWARD_DESCRIPTION = "グレードに応じたロール報酬を表示します"
PRESTIGE_REWARD_DESCRIPTION = "プレステージに応じたロール報酬を表示します"
NO_REWARD_ROLES = "報酬ロールは設定されていません。"


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

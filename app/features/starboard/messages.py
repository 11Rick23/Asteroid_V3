from __future__ import annotations

GROUP_DESCRIPTION = "スターボード関連のコマンド"
SETUP_DESCRIPTION = "旧スターボードを再作成"
SETUP_GUILD_CHANNEL_ONLY = "サーバー内チャンネルで実行してください。"
SETUP_CHANNEL_MISSING = "スターボードチャンネル設定が不足しています。"
SETUP_SAME_CHANNEL = (
    "実行チャンネルとスターボードチャンネルが同一です。別の旧スターボードチャンネルで実行してください。"
)
BOT_USER_MISSING = "BOT ユーザー情報が取得できませんでした。"
SETUP_ALREADY_RUN = "新しいスターボードチャンネルに既に BOT の投稿があります。再実行はできません。"
SOURCE_READ_FORBIDDEN = "旧スターボードチャンネルのメッセージ取得権限がありません。処理を中断しました。"
SOURCE_READ_FAILED = "旧スターボードチャンネルのメッセージ取得に失敗しました。処理を中断しました。"
DESTINATION_SEND_FORBIDDEN = "新しいスターボードチャンネルへの送信権限がありません。処理を中断しました。"
DESTINATION_SEND_FAILED = "新しいスターボードチャンネルへの送信に失敗しました。処理を中断しました。"
RANDOM_DESCRIPTION = "ランダムなスターボードを送信"
RANDOM_NOT_FOUND = "ランダムなスターボードを取得できませんでした。"
GUILD_ONLY = "サーバー内でのみ使用できます。"
CHANNEL_NOT_FOUND = "スターボードチャンネルが見つかりません。"
RANKING_DESCRIPTION = "スターボードのランキングを表示"
RANKING_DATA_MISSING = "ランキングを作成するための情報が不足しています。"
RANKING_TITLE = "スターボードランキング"
MOST_STARRED_MESSAGE_FIELD = "星が最も多いメッセージ"
MOST_STARRED_USER_FIELD = "星をたくさん受け取ったユーザー"
MOST_GIVEN_USER_FIELD = "星をたくさんあげたユーザー"
ORIGINAL_MESSAGE_FIELD = "元のメッセージ"
ORIGINAL_MESSAGE_LINK_LABEL = "リンク"
ATTACHMENT_FIELD = "添付ファイル"


def setup_summary(*, total_count: int, recreated_count: int, deleted_count: int) -> str:
    return (
        "スターボード再作成が完了しました。\n"
        f"対象件数: {total_count}\n"
        f"再作成件数: {recreated_count}\n"
        f"欠損削除件数: {deleted_count}"
    )


def setup_error(
    *,
    message: str,
    total_count: int,
    recreated_count: int,
    deleted_count: int,
    processed_count: int,
) -> str:
    return (
        f"{message}\n"
        f"対象件数: {total_count}\n"
        f"処理済み件数: {processed_count}\n"
        f"再作成件数: {recreated_count}\n"
        f"欠損削除件数: {deleted_count}"
    )


def message_ranking_line(*, emoji: str, guild_id: int, channel_id: int, message_id: int, stars: int) -> str:
    return f"{emoji} : [{message_id}](https://discord.com/channels/{guild_id}/{channel_id}/{message_id}) (⭐️ {stars})"


def user_ranking_line(*, emoji: str, user_id: int, stars: int, compact: bool = False) -> str:
    separator = "" if compact else " "
    return f"{emoji} : <@{user_id}>{separator}(⭐️ {stars})"


def original_message_link(*, jump_url: str) -> str:
    return f"[{ORIGINAL_MESSAGE_LINK_LABEL}]({jump_url})"


def starboard_content(*, emoji: str, star_amount: int, channel_mention: str) -> str:
    return f"{emoji} **{star_amount}** {channel_mention}"

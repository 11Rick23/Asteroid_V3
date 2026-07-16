from __future__ import annotations

VOICE_XP_BUTTON_LABEL = "VC経験値を獲得する"
VOICE_XP_NOT_EARNED = "VC経験値を獲得していません"
VOICE_XP_PANEL_TITLE = "VC経験値獲得はこちら"
VOICE_XP_PANEL_DESCRIPTION = "ボタンを押すとVC経験値を獲得します"
VOICE_XP_LIMIT_TITLE = "VC経験値獲得上限到達！"
SETUP_VOICE_XP_DESCRIPTION = "VC経験値獲得用のボタンを設置します"
CHANNEL_NOT_MESSAGEABLE = "このチャンネルには送信できません。"
VOICE_XP_BUTTON_INSTALLED = "VC経験値獲得用のボタンを設置しました！"
CLAIM_DESCRIPTION = "VC経験値を獲得します"


def limit_reached(*, member_mention: str) -> str:
    return (
        f"**{member_mention}さんはVC経験値獲得上限に到達しました！\n"
        "VC経験値を更に獲得するには`経験値を獲得する`ボタンを押すか、"
        "`/claim_voice_xp` コマンドを実行してください！**"
    )


def claimed(*, user_mention: str, voice_shard: str, voice_power: str, bonus_shard: str) -> str:
    return (
        f"{user_mention} ボイスシャードを`{voice_shard}`獲得しました\n"
        f"ボイスパワーを`{voice_power}`獲得しました\n"
        f"ボイスボーナスシャードを`{bonus_shard}`獲得しました"
    )

from __future__ import annotations

AUTH_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、認証システムは現在利用できません。時間を空けてもう一度ご確認ください。"
)

WELCOME_ASCII = """```
█▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█
█░░╦ ╦╔╗╦ ╔╗╔╗╔╦╗╔╗░░█
█░░║║║╠─║ ║ ║║║║║╠─░░█
█░░╚╩╝╚╝╚╝╚╝╚╝╩ ╩╚╝░░█
█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█
```"""

DELETE_DIGIT_LABEL = "1文字消す"
CLEAR_LABEL = "クリア"
SUBMIT_LABEL = "検証"
START_LABEL = "認証"
AUTH_MISMATCH = "数字が一致しませんでした。もう一度入力してください。"
AUTH_GUILD_ONLY = "サーバー内で認証してください。"
AUTH_OWNER_ONLY = "この認証画面はあなた専用です。"
AUTH_NOT_ENTERED = "未入力"
AUTH_PANEL_CONTENT = "# サーバーへようこそ！\nチャットを開始する前に、ボタンを押してBOT検証を行ってください。"


def authentication_completed() -> str:
    return f"# 検証に成功しました！\n{WELCOME_ASCII}"


def authentication_challenge(*, entered_number: str, error_message: str | None) -> str:
    error_text = f"\n\n**{error_message}**" if error_message else ""
    return (
        "# BOT検証を行います\n"
        "画像に書かれた数字を、下のボタンで順番に入力してください。\n\n"
        f"## **入力:** `{entered_number}`"
        f"{error_text}"
    )

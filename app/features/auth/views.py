from __future__ import annotations

import random
from logging import getLogger

import discord
from captcha.image import ImageCaptcha

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot
from app.features.welcomer.service import send_first_welcome

logger = getLogger(__name__)

WELCOME_ASCII = """```
█▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█
█░░╦ ╦╔╗╦ ╔╗╔╗╔╦╗╔╗░░█
█░░║║║╠─║ ║ ║║║║║╠─░░█
█░░╚╩╝╚╝╚╝╚╝╚╝╩ ╩╚╝░░█
█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█
```"""


async def complete_authentication(bot: AsteroidBot, interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        return False

    unauthorized_role = interaction.guild.get_role(bot.config.auth.unauthorized_role_id)
    if unauthorized_role is not None:
        await interaction.user.remove_roles(
            unauthorized_role,
            reason=f"[{generate_timestamp()}] 認証されました。",
        )
        logger.debug(
            "未認証ロールを削除しました: "
            f"guild_id={interaction.guild.id} user_id={interaction.user.id} role_id={unauthorized_role.id}"
        )
    else:
        logger.warning(
            "未認証ロールが見つかりませんでした: "
            f"guild_id={interaction.guild.id} role_id={bot.config.auth.unauthorized_role_id} "
            f"user_id={interaction.user.id}"
        )

    await send_first_welcome(interaction.user)
    logger.debug(f"初回ウェルカムを送信しました: guild_id={interaction.guild.id} user_id={interaction.user.id}")
    return True


async def auth(bot: AsteroidBot, interaction: discord.Interaction) -> None:
    logger.debug(
        f"認証を開始しました: guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"channel_id={interaction.channel_id} user_id={interaction.user.id if interaction.user is not None else None}"
    )
    captcha = ImageCaptcha(320, 120, None, (50, 60, 70, 80))
    number = str(random.randint(0, 99999))
    number = number.replace("1", random.choice("0234")).replace("7", random.choice("5689"))
    image = captcha.generate(number, "png")
    file = discord.File(image, filename="captcha.png")

    await interaction.response.send_message(
        file=file,
        view=AuthChallengeView(bot, number, interaction.user.id),
        ephemeral=True,
    )


class AuthDigitButton(discord.ui.Button["AuthChallengeView"]):
    def __init__(self, digit: str) -> None:
        super().__init__(
            label=digit,
            style=discord.ButtonStyle.secondary,
            custom_id=f"auth_digit:{digit}",
        )
        self.digit = digit

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None:
            return
        if len(view.entered_number) < len(view.expected_number):
            view.entered_number += self.digit
        await view.refresh(interaction)


class AuthDeleteButton(discord.ui.Button["AuthChallengeView"]):
    def __init__(self) -> None:
        super().__init__(label="1文字消す", style=discord.ButtonStyle.blurple, custom_id="auth_delete")

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None:
            return
        view.entered_number = view.entered_number[:-1]
        await view.refresh(interaction)


class AuthClearButton(discord.ui.Button["AuthChallengeView"]):
    def __init__(self) -> None:
        super().__init__(label="クリア", style=discord.ButtonStyle.danger, custom_id="auth_clear")

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None:
            return
        view.entered_number = ""
        view.error_message = None
        await view.refresh(interaction)


class AuthSubmitButton(discord.ui.Button["AuthChallengeView"]):
    def __init__(self) -> None:
        super().__init__(label="検証", style=discord.ButtonStyle.success, custom_id="auth_submit")

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None:
            return
        if view.entered_number != view.expected_number:
            logger.debug(
                "認証に失敗しました: "
                f"guild_id={interaction.guild_id} user_id={interaction.user.id} "
                f"entered_length={len(view.entered_number)}"
            )
            view.entered_number = ""
            view.error_message = "数字が一致しませんでした。もう一度入力してください。"
            await view.refresh(interaction)
            return

        logger.debug(f"認証に成功しました: guild_id={interaction.guild_id} user_id={interaction.user.id}")
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("サーバー内で認証してください。", ephemeral=True)
            return
        await interaction.response.defer()
        await complete_authentication(view.bot, interaction)
        view.completed = True
        view.stop()
        view.build()
        await interaction.edit_original_response(view=view)


class AuthChallengeView(GuildScopedLayoutView):
    def __init__(self, bot: AsteroidBot, number_in_str: str, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.expected_number = number_in_str
        self.owner_id = owner_id
        self.entered_number = ""
        self.error_message: str | None = None
        self.completed = False
        self.build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("この認証画面はあなた専用です。", ephemeral=True)
        return False

    def build(self) -> None:
        self.clear_items()
        if self.completed:
            self.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(f"# 検証に成功しました！\n{WELCOME_ASCII}"),
                    accent_color=AsteroidColor.SUCCESS,
                )
            )
            return

        entered_number = self.entered_number or "未入力"
        error_text = f"\n\n**{self.error_message}**" if self.error_message else ""
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    "# BOT検証を行います\n"
                    "画像に書かれた数字を、下のボタンで順番に入力してください。\n\n"
                    f"## **入力:** `{entered_number}`"
                    f"{error_text}"
                ),
                discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://captcha.png")),
                discord.ui.ActionRow(*(AuthDigitButton(str(digit)) for digit in range(1, 6))),
                discord.ui.ActionRow(*(AuthDigitButton(str(digit)) for digit in (6, 7, 8, 9, 0))),
                discord.ui.ActionRow(AuthDeleteButton(), AuthClearButton(), AuthSubmitButton()),
                accent_color=AsteroidColor.DARK_GREEN,
            )
        )

    async def refresh(self, interaction: discord.Interaction) -> None:
        self.build()
        await interaction.response.edit_message(view=self)


class AuthStartButton(discord.ui.Button["AuthButton"]):
    def __init__(self, bot: AsteroidBot) -> None:
        super().__init__(
            label="認証",
            style=discord.ButtonStyle.green,
            custom_id="auth_button",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        await auth(self.bot, interaction)


class AuthButton(GuildScopedLayoutView):
    def __init__(self, bot: AsteroidBot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(
                    "# サーバーへようこそ！\nチャットを開始する前に、ボタンを押してBOT検証を行ってください。"
                ),
                discord.ui.ActionRow(AuthStartButton(bot)),
                accent_color=AsteroidColor.DARK_GREEN,
            )
        )

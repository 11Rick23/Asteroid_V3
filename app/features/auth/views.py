from __future__ import annotations

import random
from logging import getLogger

import discord
from captcha.image import ImageCaptcha

from app.common.guild_scope import GuildScopedModal, GuildScopedView
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


class AuthInput(GuildScopedModal):
    def __init__(self, bot: AsteroidBot, number_in_str: str):
        super().__init__(title="認証", timeout=None)
        self.bot = bot
        self.number_in_str = number_in_str
        self.numbers = discord.ui.TextInput(
            label="画像の数字",
            placeholder="12345",
            max_length=5,
        )
        self.add_item(self.numbers)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if str(self.numbers.value) == self.number_in_str:
            logger.debug(
                f"認証に成功しました: guild_id={interaction.guild.id if interaction.guild is not None else None} "
                f"user_id={interaction.user.id if interaction.user is not None else None}"
            )
            if interaction.guild is None or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    "サーバー内で認証してください。",
                    ephemeral=True,
                )
                return
            unauthorized_role = interaction.guild.get_role(self.bot.config.auth.unauthorized_role_id)
            if unauthorized_role is not None:
                await interaction.user.remove_roles(
                    unauthorized_role,
                    reason=f"[{generate_timestamp()}] 認証されました。",
                )
                logger.debug(
                    "未認証ロールを削除しました: "
                    f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
                    f"user_id={interaction.user.id if interaction.user is not None else None} "
                    f"role_id={unauthorized_role.id}"
                )
            else:
                logger.warning(
                    "未認証ロールが見つかりませんでした: "
                    f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
                    f"role_id={self.bot.config.auth.unauthorized_role_id} "
                    f"user_id={interaction.user.id if interaction.user is not None else None}"
                )
            await interaction.response.send_message(
                WELCOME_ASCII,
                ephemeral=True,
            )
            await send_first_welcome(interaction.user)
            logger.debug(
                "初回ウェルカムを送信しました: "
                f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
                f"user_id={interaction.user.id}"
            )
            return

        logger.debug(
            f"認証に失敗しました: guild_id={interaction.guild.id if interaction.guild is not None else None} "
            f"user_id={interaction.user.id if interaction.user is not None else None}"
        )
        await interaction.response.send_message(
            "認証に失敗しました…… もう一度お試しください。",
            ephemeral=True,
        )


class InputButton(discord.ui.Button):
    def __init__(self, bot: AsteroidBot, number_in_str: str):
        super().__init__(
            label="数字を入力",
            style=discord.ButtonStyle.blurple,
            custom_id="input_auth_button",
        )
        self.bot = bot
        self.number_in_str = number_in_str

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AuthInput(self.bot, self.number_in_str))


async def auth(bot: AsteroidBot, interaction: discord.Interaction) -> None:
    logger.debug(
        f"認証を開始しました: guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"channel_id={interaction.channel_id} user_id={interaction.user.id if interaction.user is not None else None}"
    )
    captcha = ImageCaptcha(160, 60)
    number = str(random.randint(0, 99999))
    number = number.replace("1", random.choice("0234")).replace("7", random.choice("5689"))
    image = captcha.generate(number, "png")
    file = discord.File(image, filename="captcha.png")

    embed = discord.Embed(
        title="認証してください！",
        description="ボタンを押して画像に書かれた数字を入力してください。",
    )
    embed.set_image(url="attachment://captcha.png")

    view = GuildScopedView(timeout=300)
    view.add_item(InputButton(bot, number))
    await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)


class AuthButton(GuildScopedView):
    def __init__(self, bot: AsteroidBot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @discord.ui.button(label="認証", style=discord.ButtonStyle.green, custom_id="auth_button")
    async def callback(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await auth(self.bot, interaction)

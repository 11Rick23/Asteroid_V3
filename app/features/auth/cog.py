from __future__ import annotations

import random
from logging import getLogger

import discord
from captcha.image import ImageCaptcha
from discord import app_commands
from discord.ext import commands

from app.common.command_groups import get_bot, register_setup_command
from app.common.constants import AsteroidColor
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


class AuthInput(discord.ui.Modal):
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
            logger.info(
                f"認証に成功しました: guild_id={interaction.guild.id if interaction.guild is not None else None} "
                f"user_id={interaction.user.id if interaction.user is not None else None}"
            )
            unauthorized_role = interaction.guild.get_role(self.bot.config.auth.unauthorized_role_id)
            if unauthorized_role is not None:
                await interaction.user.remove_roles(
                    unauthorized_role,
                    reason=f"[{generate_timestamp()}] 認証されました。",
                )
                logger.info(
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
            if isinstance(interaction.user, discord.Member):
                await send_first_welcome(interaction.user)
                logger.info(
                    "初回ウェルカムを送信しました: "
                    f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
                    f"user_id={interaction.user.id}"
                )
            return

        logger.info(
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
    logger.info(
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

    view = discord.ui.View(timeout=300)
    view.add_item(InputButton(bot, number))
    await interaction.response.send_message(embed=embed, file=file, view=view, ephemeral=True)


class AuthButton(discord.ui.View):
    def __init__(self, bot: AsteroidBot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot

    @discord.ui.button(label="認証", style=discord.ButtonStyle.green, custom_id="auth_button")
    async def callback(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await auth(self.bot, interaction)


class Authenticator(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(AuthButton(self.bot, timeout=None))


@app_commands.command(name="auth", description="認証用のボタンを設置します。")
@app_commands.guild_only()
async def setup_auth(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    embed = discord.Embed(
        title="下のボタンを押して認証してください！",
        description="下のボタンを押して認証を開始してください。",
        color=AsteroidColor.DARK_GREEN,
    )
    await interaction.channel.send(embed=embed, view=AuthButton(bot, timeout=None))
    logger.info(
        f"認証ボタンを設置しました: guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"channel_id={interaction.channel_id} user_id={interaction.user.id if interaction.user is not None else None}"
    )
    await interaction.response.send_message("認証用のボタンを設置しました！", ephemeral=True)


async def setup(bot: AsteroidBot) -> None:
    register_setup_command(bot, setup_auth)
    await bot.add_cog(Authenticator(bot))

from __future__ import annotations

import asyncio
import random
import time
from logging import getLogger

import discord

from app.common.constants import AsteroidColor
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger("asteroid.features.free_category")

op_permissions = discord.PermissionOverwrite(
    manage_channels=True,
    create_public_threads=True,
    create_private_threads=True,
    manage_messages=True,
    manage_threads=True,
)

block_permissions = discord.PermissionOverwrite(
    view_channel=False,
    manage_channels=False,
    create_public_threads=False,
    create_private_threads=False,
    manage_messages=False,
    manage_threads=False,
)


def decorate_int(target: int) -> str:
    if 11 <= target <= 13:
        return f"{target}th"
    if target % 10 == 1:
        return f"{target}st"
    if target % 10 == 2:
        return f"{target}nd"
    if target % 10 == 3:
        return f"{target}rd"
    return f"{target}th"


class FreeCategoryService:
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.bump_cooldown_channel_ids: set[int] = set()
        self.creation_cooldown_user_ids: set[int] = set()
        self.edit_cooldowns: dict[int, float] = {}

    def get_creation_cooldown_seconds(self) -> int:
        return int(self.bot.config.get("text_create_channel_cooldown_seconds", 86400) or 86400)

    def get_edit_cooldown_retry_after(self, channel_id: int) -> float:
        expires_at = self.edit_cooldowns.get(channel_id, 0.0)
        retry_after = expires_at - time.monotonic()
        if retry_after <= 0:
            self.edit_cooldowns.pop(channel_id, None)
            return 0.0
        return retry_after

    def start_edit_cooldown(self, channel_id: int, seconds: float = 600.0) -> None:
        self.edit_cooldowns[channel_id] = time.monotonic() + seconds

    def is_creation_on_cooldown(self, user_id: int) -> bool:
        return user_id in self.creation_cooldown_user_ids

    def is_bump_on_cooldown(self, channel_id: int) -> bool:
        return channel_id in self.bump_cooldown_channel_ids

    def start_creation_cooldown(self, user_id: int) -> None:
        self.creation_cooldown_user_ids.add(user_id)
        asyncio.create_task(
            self._clear_cooldown_after(self.creation_cooldown_user_ids, user_id, self.get_creation_cooldown_seconds())
        )

    def start_bump_cooldown(self, channel_id: int, seconds: int) -> None:
        self.bump_cooldown_channel_ids.add(channel_id)
        asyncio.create_task(self._clear_cooldown_after(self.bump_cooldown_channel_ids, channel_id, seconds))

    async def _clear_cooldown_after(self, targets: set[int], target_id: int, seconds: int) -> None:
        await asyncio.sleep(max(0, seconds))
        targets.discard(target_id)

    def get_manageable_text_channel(self, interaction: discord.Interaction) -> discord.TextChannel | None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return None
        if not channel.permissions_for(interaction.user).manage_channels:
            return None
        return channel

    async def ensure_manageable_text_channel(
        self, interaction: discord.Interaction, *, ephemeral: bool = True
    ) -> discord.TextChannel | None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "このコマンドはテキストチャンネルでのみ使えます。",
                ephemeral=ephemeral,
            )
            return None
        if not channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message(
                "あなたはこのチャンネルの管理者ではありません。",
                ephemeral=ephemeral,
            )
            return None
        return channel

    def get_category(self, guild: discord.Guild, config_key: str) -> discord.CategoryChannel | None:
        category_id = int(self.bot.config.get(config_key, 0) or 0)
        channel = guild.get_channel(category_id)
        return channel if isinstance(channel, discord.CategoryChannel) else None

    def get_reserved_channel_ids(self) -> set[int]:
        return {
            int(self.bot.config.get("text_create_channel_id", 0) or 0),
            int(self.bot.config.get("side_button_channel_id", 0) or 0),
        } - {0}

    def get_category_channels(
        self, category: discord.CategoryChannel, *, managed_only: bool = False
    ) -> list[discord.abc.GuildChannel]:
        if not managed_only:
            return list(category.channels)
        reserved_ids = self.get_reserved_channel_ids()
        return [channel for channel in category.channels if channel.id not in reserved_ids]

    def get_free_category_min_position(self, category: discord.CategoryChannel) -> int:
        reserved_ids = self.get_reserved_channel_ids()
        return 1 if any(channel.id in reserved_ids for channel in category.channels) else 0

    async def move_channel_to_managed_end(
        self, channel: discord.abc.GuildChannel, category: discord.CategoryChannel, *, reason: str
    ) -> None:
        anchors = [
            category.guild.get_channel(channel_id)
            for channel_id in self.get_reserved_channel_ids()
            if category.guild.get_channel(channel_id) is not None
        ]
        anchors = [anchor for anchor in anchors if getattr(anchor, "category_id", None) == category.id]
        if anchors:
            anchor = min(anchors, key=lambda item: item.position)
            await channel.move(before=anchor, category=category, reason=reason)
            return
        await channel.move(end=True, category=category, reason=reason)

    async def archive_channel(self, channel: discord.TextChannel, reason: str) -> None:
        archive_category = self.get_category(channel.guild, "fc_archive_category_id")
        if archive_category is None:
            raise ValueError("`fc_archive_category_id` が未設定です。")

        await channel.edit(
            category=archive_category,
            sync_permissions=True,
            reason=f"[{generate_timestamp()}] {reason}",
            position=0,
        )

        embed = discord.Embed(
            color=AsteroidColor.DARK_BLUE,
            title="このチャンネルはアーカイブ行きになりました。",
        )
        embed.add_field(name="理由", value=reason, inline=False)
        await channel.send(embed=embed)

    async def prepare_free_category_slot(self, guild: discord.Guild) -> None:
        free_category = self.get_category(guild, "free_category_id")
        minor_category = self.get_category(guild, "minor_category_id")
        if free_category is None:
            raise ValueError("`free_category_id` が未設定です。")
        if minor_category is None:
            raise ValueError("`minor_category_id` が未設定です。")

        free_limit = int(self.bot.config.get("free_category_channel_limit", 20) or 20)
        free_channels = self.get_category_channels(free_category, managed_only=True)
        if free_limit > 0 and len(free_channels) >= free_limit and free_channels:
            channel_to_move = free_channels[-1]
            await channel_to_move.move(
                beginning=True,
                category=minor_category,
                reason=f"[{generate_timestamp()}] フリーチャンネル作成前の整理。",
            )

        minor_limit = int(self.bot.config.get("minor_category_channel_limit", 15) or 15)
        minor_channels = self.get_category_channels(minor_category, managed_only=True)
        if minor_limit > 0 and len(minor_channels) > minor_limit and minor_channels:
            channel_to_archive = minor_channels[-1]
            if isinstance(channel_to_archive, discord.TextChannel):
                await self.archive_channel(channel_to_archive, "マイナーカテゴリーの最下部に位置するため。")

    async def create_channel(self, interaction: discord.Interaction, channel_name: str) -> discord.TextChannel:
        guild = interaction.guild
        if guild is None:
            raise ValueError("サーバー内でのみ利用できます。")

        free_category = self.get_category(guild, "free_category_id")
        if free_category is None:
            raise ValueError("`free_category_id` が未設定です。")

        clean_name = channel_name.strip()
        if not clean_name:
            raise ValueError("チャンネル名を入力してください。")

        await self.prepare_free_category_slot(guild)

        overwrites = dict(free_category.overwrites)
        overwrites[interaction.user] = op_permissions
        reason = f"[{generate_timestamp()}] フリーチャンネル作成。"
        new_channel = await guild.create_text_channel(
            name=clean_name,
            category=free_category,
            overwrites=overwrites,
            topic=f"{interaction.user.mention} のチャンネルです！ \n作成日時 : {generate_timestamp()}",
            reason=reason,
        )
        await self.move_channel_to_managed_end(new_channel, free_category, reason=reason)
        self.start_creation_cooldown(interaction.user.id)
        return new_channel

    async def maybe_auto_bump(self, message: discord.Message) -> None:
        if (
            message.author.bot
            or message.guild is None
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.category is None
            or self.is_bump_on_cooldown(message.channel.id)
        ):
            return

        hall_of_fame = self.get_category(message.guild, "hall_of_fame_category_id")
        free_category = self.get_category(message.guild, "free_category_id")
        minor_category = self.get_category(message.guild, "minor_category_id")
        current_category = message.channel.category

        if hall_of_fame and current_category.id == hall_of_fame.id:
            bump_chance = float(self.bot.config.get("hall_of_fame_bump_chance", 0.01) or 0.01)
            min_position = 0
            category_move_chance = 0.0
            category_flag = "hall_of_fame"
        elif free_category and current_category.id == free_category.id:
            bump_chance = float(self.bot.config.get("free_category_bump_chance", 0.05) or 0.05)
            min_position = self.get_free_category_min_position(current_category)
            category_move_chance = float(self.bot.config.get("category_move_chance", 0.25) or 0.25)
            category_flag = "free_category"
        elif minor_category and current_category.id == minor_category.id:
            bump_chance = float(self.bot.config.get("minor_category_bump_chance", 1.0) or 1.0)
            min_position = 0
            category_move_chance = float(self.bot.config.get("category_move_chance", 0.25) or 0.25)
            category_flag = "minor_category"
        else:
            return

        if random.random() > bump_chance:
            self.start_bump_cooldown(message.channel.id, int(self.bot.config.get("bump_cooldown_seconds", 30) or 30))
            return

        self.start_bump_cooldown(
            message.channel.id,
            int(self.bot.config.get("bump_cooldown_seconds_after_bump", 900) or 900),
        )

        channel_position = current_category.channels.index(message.channel)
        if min_position < channel_position:
            await message.channel.move(
                beginning=True,
                offset=channel_position - 1,
                reason=f"[{generate_timestamp()}] フリーカテゴリの自動BUMP。",
            )
            if category_flag == "free_category":
                before_label = decorate_int(channel_position)
                after_label = decorate_int(channel_position - 1)
            else:
                before_label = decorate_int(channel_position + 1)
                after_label = decorate_int(channel_position)

            embed = discord.Embed(
                color=AsteroidColor.LIGHT_GREEN,
                title="チャンネルがBUMPされました！",
                description=f"`{before_label}` -> `{after_label}`",
            )
            await message.channel.send(embed=embed)
            return

        if channel_position != min_position or random.random() > category_move_chance:
            return

        if category_flag == "free_category":
            if hall_of_fame is None:
                return
            hall_limit = int(self.bot.config.get("hall_of_fame_channel_limit", 5) or 5)
            hall_channels = self.get_category_channels(hall_of_fame, managed_only=True)
            if hall_limit > 0 and len(hall_channels) >= hall_limit and hall_channels:
                return_channel = hall_channels[-1]
                await return_channel.move(
                    beginning=True,
                    category=current_category,
                    offset=self.get_free_category_min_position(current_category),
                    reason=f"[{generate_timestamp()}] 殿堂入りチャンネルの整理。",
                )
            await self.move_channel_to_managed_end(
                message.channel,
                hall_of_fame,
                reason=f"[{generate_timestamp()}] 殿堂入りしました。",
            )
            embed = discord.Embed(
                color=AsteroidColor.DARK_PURPLE,
                title="おめでとうございます！",
                description=f"{message.channel.mention} は殿堂入りしました！",
            )
            await message.channel.send(embed=embed)
            return

        if category_flag == "minor_category":
            if free_category is None:
                return
            free_limit = int(self.bot.config.get("free_category_channel_limit", 20) or 20)
            free_channels = self.get_category_channels(free_category, managed_only=True)
            if free_limit > 0 and len(free_channels) >= free_limit and free_channels:
                return_channel = free_channels[-1]
                await return_channel.move(
                    beginning=True,
                    category=current_category,
                    reason=f"[{generate_timestamp()}] フリーカテゴリ昇格時の整理。",
                )
            await self.move_channel_to_managed_end(
                message.channel,
                free_category,
                reason=f"[{generate_timestamp()}] フリーカテゴリへ昇格しました。",
            )
            embed = discord.Embed(
                color=AsteroidColor.DARK_PURPLE,
                title="おめでとうございます！",
                description=f"{message.channel.mention} はフリーカテゴリーに昇格しました！",
            )
            await message.channel.send(embed=embed)


def get_free_category_service(bot: AsteroidBot) -> FreeCategoryService:
    service = bot.services.get("free_category")
    if isinstance(service, FreeCategoryService):
        return service

    new_service = FreeCategoryService(bot)
    bot.services["free_category"] = new_service
    return new_service

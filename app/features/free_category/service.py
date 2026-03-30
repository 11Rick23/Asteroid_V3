from __future__ import annotations

import asyncio
import random
import time
from logging import getLogger

import discord

from app.common.constants import AsteroidColor
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger(__name__)

op_permissions = discord.PermissionOverwrite(
    manage_channels=True,
    create_public_threads=True,
    create_private_threads=True,
    manage_messages=True,
    pin_messages=True,
    manage_threads=True,
)

block_permissions = discord.PermissionOverwrite(
    view_channel=False,
    manage_channels=False,
    create_public_threads=False,
    create_private_threads=False,
    manage_messages=False,
    pin_messages=False,
    manage_threads=False,
)


def decorate_int(target: int) -> str:
    """整数を順位表示用の序数文字列に変換する。"""
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
    """フリーカテゴリー機能の状態管理と実処理をまとめたサービス。"""

    def __init__(self, bot: AsteroidBot):
        """Bot 参照と各種クールダウン状態を初期化する。"""
        self.bot = bot
        self.bump_cooldown_channel_ids: set[int] = set()
        self.creation_cooldown_user_ids: set[int] = set()
        self.edit_cooldowns: dict[int, float] = {}

    def get_creation_cooldown_seconds(self) -> int:
        """チャンネル作成クールダウンの秒数を返す。"""
        return self.bot.config.free_category.text_create_channel_cooldown_seconds

    def get_edit_cooldown_retry_after(self, channel_id: int) -> float:
        """編集クールダウンの残り秒数を返し、期限切れなら状態を消す。"""
        expires_at = self.edit_cooldowns.get(channel_id, 0.0)
        retry_after = expires_at - time.monotonic()
        if retry_after <= 0:
            self.edit_cooldowns.pop(channel_id, None)
            return 0.0
        return retry_after

    def start_edit_cooldown(self, channel_id: int, seconds: float = 600.0) -> None:
        """指定チャンネルの編集クールダウンを開始する。"""
        self.edit_cooldowns[channel_id] = time.monotonic() + seconds

    def is_creation_on_cooldown(self, user_id: int) -> bool:
        """ユーザーがチャンネル作成クールダウン中かを返す。"""
        return user_id in self.creation_cooldown_user_ids

    def is_bump_on_cooldown(self, channel_id: int) -> bool:
        """チャンネルが自動 BUMP クールダウン中かを返す。"""
        return channel_id in self.bump_cooldown_channel_ids

    def start_creation_cooldown(self, user_id: int) -> None:
        """ユーザーのチャンネル作成クールダウンを開始する。"""
        self.creation_cooldown_user_ids.add(user_id)
        asyncio.create_task(
            self._clear_cooldown_after(self.creation_cooldown_user_ids, user_id, self.get_creation_cooldown_seconds())
        )

    def start_bump_cooldown(self, channel_id: int, seconds: int) -> None:
        """チャンネルの自動 BUMP クールダウンを開始する。"""
        self.bump_cooldown_channel_ids.add(channel_id)
        asyncio.create_task(self._clear_cooldown_after(self.bump_cooldown_channel_ids, channel_id, seconds))

    async def _clear_cooldown_after(self, targets: set[int], target_id: int, seconds: int) -> None:
        """指定秒数後にクールダウン対象から ID を取り除く。"""
        await asyncio.sleep(max(0, seconds))
        targets.discard(target_id)

    def get_manageable_text_channel(self, interaction: discord.Interaction) -> discord.TextChannel | None:
        """ユーザーが管理できるテキストチャンネルならチャンネルを返す。"""
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return None
        if not channel.permissions_for(interaction.user).manage_channels:
            return None
        return channel

    async def ensure_manageable_text_channel(
        self, interaction: discord.Interaction, *, ephemeral: bool = True
    ) -> discord.TextChannel | None:
        """管理可能なテキストチャンネルであることを確認し、失敗時はエラ〜メッセージを送信する。"""
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

    def get_category(self, guild: discord.Guild, category_id: int) -> discord.CategoryChannel | None:
        """ID からカテゴリを取得し、カテゴリでなければ `None` を返す。"""
        channel = guild.get_channel(category_id)
        return channel if isinstance(channel, discord.CategoryChannel) else None

    def get_reserved_channel_ids(self) -> set[int]:
        """自動整列から除外するチャンネル ID を返す。"""
        return {
            self.bot.config.free_category.text_create_channel_id,
        } - {0}  # 0 は未設定を意味するため、セットから除外する

    def get_channels_in_category(
        self, category: discord.CategoryChannel, *, managed_only: bool = False
    ) -> list[discord.abc.GuildChannel]:
        """カテゴリ内チャンネル一覧を返し、必要なら予約チャンネルを除外する。"""
        if not managed_only:
            return list(category.channels)
        reserved_ids = self.get_reserved_channel_ids()
        return [channel for channel in category.channels if channel.id not in reserved_ids]

    def get_free_category_min_position(self, category: discord.CategoryChannel) -> int:
        """フリーカテゴリーでチャンネルが入れる最上位位置を返す。"""
        reserved_ids = self.get_reserved_channel_ids()
        return 1 if any(channel.id in reserved_ids for channel in category.channels) else 0

    async def archive_channel(self, channel: discord.TextChannel, reason: str) -> None:
        """チャンネルをアーカイブカテゴリへ移動し、通知メッセージを送る。"""
        archive_category = self.get_category(channel.guild, self.bot.config.free_category.fc_archive_category_id)
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
        """新規作成前にカテゴリ上限を調整し、必要なら移動やアーカイブを行う。"""
        free_category = self.get_category(guild, self.bot.config.free_category.free_category_id)
        minor_category = self.get_category(guild, self.bot.config.free_category.minor_category_id)
        if free_category is None:
            raise ValueError("`free_category_id` が未設定です。")
        if minor_category is None:
            raise ValueError("`minor_category_id` が未設定です。")

        free_limit = self.bot.config.free_category.free_category_channel_limit
        free_channels = self.get_channels_in_category(free_category, managed_only=True)
        if free_limit > 0 and len(free_channels) >= free_limit and free_channels:
            channel_to_move = free_channels[-1]
            await channel_to_move.move(
                beginning=True,
                category=minor_category,
                reason=f"[{generate_timestamp()}] フリーチャンネル作成前の整理。",
            )

        minor_limit = self.bot.config.free_category.minor_category_channel_limit
        minor_channels = self.get_channels_in_category(minor_category, managed_only=True)
        if minor_limit > 0 and len(minor_channels) > minor_limit and minor_channels:
            channel_to_archive = minor_channels[-1]
            if isinstance(channel_to_archive, discord.TextChannel):
                await self.archive_channel(channel_to_archive, "マイナーカテゴリーの最下部に位置するため。")

    async def create_channel(self, interaction: discord.Interaction, channel_name: str) -> discord.TextChannel:
        """フリーカテゴリーに新しいテキストチャンネルを作成する。"""
        guild = interaction.guild
        if guild is None:
            raise ValueError("サーバー内でのみ利用できます。")

        free_category = self.get_category(guild, self.bot.config.free_category.free_category_id)
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
        await new_channel.move(end=True, offset=-3, category=free_category, reason=reason)
        self.start_creation_cooldown(interaction.user.id)
        return new_channel

    async def maybe_auto_bump(self, message: discord.Message) -> None:
        """メッセージ送信を契機にチャンネルの BUMP やカテゴリ昇格を試みる。"""
        if (
            message.author.bot
            or message.guild is None
            or not isinstance(message.channel, discord.TextChannel)
            or message.channel.category is None
            or self.is_bump_on_cooldown(message.channel.id)
        ):
            return

        hall_of_fame = self.get_category(message.guild, self.bot.config.free_category.hall_of_fame_category_id)
        free_category = self.get_category(message.guild, self.bot.config.free_category.free_category_id)
        minor_category = self.get_category(message.guild, self.bot.config.free_category.minor_category_id)
        current_category = message.channel.category

        if hall_of_fame and current_category.id == hall_of_fame.id:
            bump_chance = self.bot.config.free_category.hall_of_fame_bump_chance
            min_position = 0
            category_move_chance = 0.0
            category_flag = "hall_of_fame"
        elif free_category and current_category.id == free_category.id:
            bump_chance = self.bot.config.free_category.free_category_bump_chance
            min_position = self.get_free_category_min_position(current_category)
            category_move_chance = self.bot.config.free_category.category_move_chance
            category_flag = "free_category"
        elif minor_category and current_category.id == minor_category.id:
            bump_chance = self.bot.config.free_category.minor_category_bump_chance
            min_position = 0
            category_move_chance = self.bot.config.free_category.category_move_chance
            category_flag = "minor_category"
        else:
            return

        if random.random() > bump_chance:
            self.start_bump_cooldown(message.channel.id, self.bot.config.free_category.bump_cooldown_seconds)
            return

        self.start_bump_cooldown(
            message.channel.id,
            self.bot.config.free_category.bump_cooldown_seconds_after_bump,
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

        # カテゴリー内の位置が最上部で、かつ一定の確率を満たした場合は、カテゴリー移動を行う
        if channel_position != min_position or random.random() > category_move_chance:
            return

        if category_flag == "free_category":
            if hall_of_fame is None:
                return
            hall_limit = self.bot.config.free_category.hall_of_fame_channel_limit
            hall_channels = self.get_channels_in_category(hall_of_fame, managed_only=True)
            if hall_limit > 0 and len(hall_channels) >= hall_limit and hall_channels:
                return_channel = hall_channels[-1]
                await return_channel.move(
                    beginning=True,
                    category=current_category,
                    offset=self.get_free_category_min_position(current_category),
                    reason=f"[{generate_timestamp()}] 殿堂入りチャンネルの整理。",
                )
            await message.channel.move(
                end=True,
                category=hall_of_fame,
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
            free_limit = self.bot.config.free_category.free_category_channel_limit
            free_channels = self.get_channels_in_category(free_category, managed_only=True)
            if free_limit > 0 and len(free_channels) >= free_limit and free_channels:
                return_channel = free_channels[-1]
                await return_channel.move(
                    beginning=True,
                    category=current_category,
                    reason=f"[{generate_timestamp()}] フリーカテゴリ昇格時の整理。",
                )
            await message.channel.move(
                end=True,
                category=free_category,
                reason=f"[{generate_timestamp()}] フリーカテゴリへ昇格しました。",
            )
            embed = discord.Embed(
                color=AsteroidColor.DARK_PURPLE,
                title="おめでとうございます！",
                description=f"{message.channel.mention} はフリーカテゴリーに昇格しました！",
            )
            await message.channel.send(embed=embed)


def get_free_category_service(bot: AsteroidBot) -> FreeCategoryService:
    """Bot に保持された free_category サービスを取得し、未作成なら生成する。"""
    service = bot.services.get("free_category")
    if isinstance(service, FreeCategoryService):
        return service

    new_service = FreeCategoryService(bot)
    bot.services["free_category"] = new_service
    return new_service

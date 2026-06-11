from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app.common.command_groups import get_bot, register_group
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

from .panel import FreeCategoryPanel
from .service import block_permissions, get_free_category_service, op_permissions
from .views import CreateChannelButtonView

logger = getLogger(__name__)

free_category_group = app_commands.Group(name="fc", description="フリーカテゴリーに関するコマンド")


class FreeCategory(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.service = get_free_category_service(bot)
        self.panel = FreeCategoryPanel(bot)
        self.initialize_panel.start()

    async def cog_load(self) -> None:
        self.bot.add_view(CreateChannelButtonView(self.service))

    async def cog_unload(self) -> None:
        self.initialize_panel.cancel()
        self.panel.unregister()

    @tasks.loop(count=1)
    async def initialize_panel(self) -> None:
        await self.panel.initialize()

    @initialize_panel.before_loop
    async def before_initialize_panel(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener("on_message")
    async def auto_bump(self, message: discord.Message) -> None:
        if not self.bot.is_operating_guild(message.guild):
            return
        await self.service.maybe_auto_bump(message)


@free_category_group.command(name="archive", description="チャンネルをアーカイブ")
@app_commands.guild_only()
async def archive(interaction: discord.Interaction) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await service.archive_channel(channel, "運営、またはチャンネル管理者による `/fc archive` コマンド")
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    logger.debug(
        f"チャンネルをアーカイブしました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id}"
    )
    await interaction.followup.send("チャンネルをアーカイブしました。", ephemeral=True)


@free_category_group.command(name="edit", description="チャンネル情報を変更")
@app_commands.rename(name="チャンネル名", topic="トピック")
@app_commands.describe(name="新しいチャンネル名", topic="新しいチャンネルトピック")
@app_commands.guild_only()
async def edit(
    interaction: discord.Interaction,
    name: str | None = None,
    topic: str | None = None,
) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    if not name and not topic:
        await interaction.response.send_message(
            "チャンネル名かチャンネルトピックのどちらか一方は必ず入力してください。",
            ephemeral=True,
        )
        return

    retry_after = service.get_edit_cooldown_retry_after(channel.id)
    if retry_after > 0:
        logger.debug(
            f"チャンネル編集をクールダウンで拒否しました: channel_id={channel.id} "
            f"user_id={interaction.user.id} retry_after={round(retry_after, 1)}"
        )
        await interaction.response.send_message(
            f"このチャンネルの編集はクールダウン中です。`{round(retry_after, 1)}秒後`に再試行してください。",
            ephemeral=True,
        )
        return

    old_name = channel.name
    old_topic = channel.topic or "未設定"
    service.start_edit_cooldown(channel.id)
    await interaction.response.defer()

    if name and not topic:
        await channel.edit(
            name=name,
            reason=f"[{generate_timestamp()}] {interaction.user.name} が {old_name} を {name} に変更しました。",
        )
        logger.debug(
            f"フリーチャンネル名を変更しました: guild_id={channel.guild.id} "
            f"channel_id={channel.id} user_id={interaction.user.id}"
        )
        embed = discord.Embed(
            color=discord.Color.random(),
            title="チャンネル名を変更しました！",
            description=f"`{old_name}` -> `{name}`",
        )
        await interaction.followup.send(embed=embed)
        return

    if topic and not name:
        await channel.edit(
            topic=topic,
            reason=f"[{generate_timestamp()}] {interaction.user.name} がトピックを変更しました。",
        )
        logger.debug(
            f"フリーチャンネルトピックを変更しました: guild_id={channel.guild.id} "
            f"channel_id={channel.id} user_id={interaction.user.id}"
        )
        embed = discord.Embed(
            color=discord.Color.random(),
            title="チャンネルトピックを変更しました！",
            description=f"`{old_topic}` -> `{topic}`",
        )
        await interaction.followup.send(embed=embed)
        return

    assert name is not None and topic is not None
    await channel.edit(
        name=name,
        topic=topic,
        reason=f"[{generate_timestamp()}] {interaction.user.name} がチャンネル名とトピックを変更しました。",
    )
    logger.debug(
        f"フリーチャンネル名とトピックを変更しました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id}"
    )
    embed = discord.Embed(
        color=discord.Color.random(),
        title="チャンネル名とトピックを変更しました！",
    )
    embed.add_field(name="name", value=f"`{old_name}` -> `{name}`", inline=False)
    embed.add_field(name="topic", value=f"`{old_topic}` -> `{topic}`", inline=False)
    await interaction.followup.send(embed=embed)


@free_category_group.command(name="block", description="指定したユーザーをブロック")
@app_commands.rename(user="ユーザー")
@app_commands.describe(user="チャンネルを閲覧できなくするユーザー")
@app_commands.guild_only()
async def block(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await channel.set_permissions(
        target=user,
        overwrite=block_permissions,
        reason=f"[{generate_timestamp()}] {interaction.user.name} が {user.name} をブロックしました。",
    )
    logger.debug(
        f"フリーチャンネルでユーザーをブロックしました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id} target_id={user.id}"
    )
    await interaction.response.send_message(f"`{user.display_name}` をブロックしました！")


@free_category_group.command(name="unblock", description="指定したユーザーのブロックを解除")
@app_commands.rename(user="ユーザー")
@app_commands.describe(user="チャンネル閲覧不可を解除するユーザー")
@app_commands.guild_only()
async def unblock(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await channel.set_permissions(
        target=user,
        overwrite=None,
        reason=f"[{generate_timestamp()}] {interaction.user.name} が {user.name} のブロックを解除しました。",
    )
    logger.debug(
        f"フリーチャンネルのブロックを解除しました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id} target_id={user.id}"
    )
    await interaction.response.send_message(f"`{user.display_name}` のブロックを解除しました！")


@free_category_group.command(name="op", description="指定したユーザーにチャンネルの管理権限を付与")
@app_commands.rename(user="ユーザー")
@app_commands.describe(user="チャンネルの管理権限を付与するユーザー")
@app_commands.guild_only()
async def op(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await channel.set_permissions(
        target=user,
        overwrite=op_permissions,
        reason=f"[{generate_timestamp()}] {interaction.user.name} が {user.name} に管理権限を付与しました。",
    )
    logger.debug(
        f"フリーチャンネル管理権限を付与しました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id} target_id={user.id}"
    )
    await interaction.response.send_message(f"`{user.display_name}` にチャンネルの管理権限を付与しました！")


@free_category_group.command(name="deop", description="指定したユーザーからチャンネルの管理権限を剥奪")
@app_commands.rename(user="ユーザー")
@app_commands.describe(user="チャンネルの管理権限を剥奪するユーザー")
@app_commands.guild_only()
async def deop(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await channel.set_permissions(
        target=user,
        overwrite=None,
        reason=f"[{generate_timestamp()}] {interaction.user.name} が {user.name} の管理権限を剥奪しました。",
    )
    logger.debug(
        f"フリーチャンネル管理権限を剥奪しました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id} target_id={user.id}"
    )
    await interaction.response.send_message(f"`{user.display_name}` からチャンネルの管理権限を剥奪しました！")


@free_category_group.command(name="purge", description="指定した件数メッセージを削除")
@app_commands.rename(count="件数")
@app_commands.describe(count="削除するメッセージの件数")
@app_commands.guild_only()
async def purge(interaction: discord.Interaction, count: app_commands.Range[int, 1, 500]) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    deleted_messages = await channel.purge(
        limit=count,
        reason=f"[{generate_timestamp()}] {interaction.user.name} が `/fc purge` を実行しました。",
    )
    logger.debug(
        f"フリーチャンネルのメッセージを削除しました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id} count={len(deleted_messages)}"
    )
    await interaction.followup.send(f"{len(deleted_messages)}件のメッセージを削除しました！", ephemeral=True)


async def setup(bot: AsteroidBot) -> None:
    get_free_category_service(bot)
    register_group(bot, free_category_group)
    await bot.add_cog(FreeCategory(bot))

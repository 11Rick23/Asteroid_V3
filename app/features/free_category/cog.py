from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app.common.command_groups import get_bot, register_group
from app.common.error_reporting import report_background_task_error
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

from . import messages
from .panel import FreeCategoryPanel
from .service import block_permissions, get_free_category_service, op_permissions
from .views import CreateChannelButtonView

logger = getLogger(__name__)

free_category_group = app_commands.Group(name="fc", description=messages.GROUP_DESCRIPTION)


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

    @initialize_panel.error
    async def initialize_panel_error(self, error: BaseException) -> None:
        await report_background_task_error(self.bot, "free_category.initialize_panel", error)

    @commands.Cog.listener("on_message")
    async def auto_bump(self, message: discord.Message) -> None:
        if not self.bot.is_operating_guild(message.guild):
            return
        await self.service.maybe_auto_bump(message)


@free_category_group.command(name="archive", description=messages.ARCHIVE_DESCRIPTION)
@app_commands.guild_only()
async def archive(interaction: discord.Interaction) -> None:
    service = get_free_category_service(get_bot(interaction))
    channel = await service.ensure_manageable_text_channel(interaction)
    if channel is None:
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await service.archive_channel(channel, messages.ARCHIVE_COMMAND_REASON)
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    logger.debug(
        f"チャンネルをアーカイブしました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id}"
    )
    await interaction.followup.send(messages.ARCHIVED, ephemeral=True)


@free_category_group.command(name="edit", description=messages.EDIT_DESCRIPTION)
@app_commands.rename(name=messages.CHANNEL_NAME_LABEL, topic=messages.TOPIC_LABEL)
@app_commands.describe(name=messages.NEW_CHANNEL_NAME_DESCRIPTION, topic=messages.NEW_TOPIC_DESCRIPTION)
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
            messages.EDIT_VALUE_REQUIRED,
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
            messages.edit_cooldown(retry_after=retry_after),
            ephemeral=True,
        )
        return

    old_name = channel.name
    old_topic = channel.topic or messages.TOPIC_UNSET
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
            title=messages.NAME_CHANGED_TITLE,
            description=messages.changed_value(old_value=old_name, new_value=name),
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
            title=messages.TOPIC_CHANGED_TITLE,
            description=messages.changed_value(old_value=old_topic, new_value=topic),
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
        title=messages.NAME_TOPIC_CHANGED_TITLE,
    )
    embed.add_field(
        name=messages.NAME_FIELD, value=messages.changed_value(old_value=old_name, new_value=name), inline=False
    )
    embed.add_field(
        name=messages.TOPIC_FIELD, value=messages.changed_value(old_value=old_topic, new_value=topic), inline=False
    )
    await interaction.followup.send(embed=embed)


@free_category_group.command(name="block", description=messages.BLOCK_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.BLOCK_USER_DESCRIPTION)
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
    await interaction.response.send_message(messages.user_blocked(display_name=user.display_name))


@free_category_group.command(name="unblock", description=messages.UNBLOCK_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.UNBLOCK_USER_DESCRIPTION)
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
    await interaction.response.send_message(messages.user_unblocked(display_name=user.display_name))


@free_category_group.command(name="op", description=messages.OP_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.OP_USER_DESCRIPTION)
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
    await interaction.response.send_message(messages.user_opped(display_name=user.display_name))


@free_category_group.command(name="deop", description=messages.DEOP_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.DEOP_USER_DESCRIPTION)
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
    await interaction.response.send_message(messages.user_deopped(display_name=user.display_name))


@free_category_group.command(name="purge", description=messages.PURGE_DESCRIPTION)
@app_commands.rename(count=messages.COUNT_LABEL)
@app_commands.describe(count=messages.PURGE_COUNT_DESCRIPTION)
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
    await interaction.followup.send(messages.messages_purged(count=len(deleted_messages)), ephemeral=True)


async def setup(bot: AsteroidBot) -> None:
    get_free_category_service(bot)
    register_group(bot, free_category_group)
    await bot.add_cog(FreeCategory(bot))

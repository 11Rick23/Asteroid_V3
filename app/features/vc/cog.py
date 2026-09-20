from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands

from app.common.command_groups import get_bot, register_group
from app.common.interaction_errors import format_rate_limited_error
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

from . import messages
from .service import blocked_permissions, get_vc_service, owner_permissions

logger = getLogger(__name__)

vc_group = app_commands.Group(name="vc", description=messages.GROUP_DESCRIPTION)


class VoiceCreateCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.service = get_vc_service(bot)

    async def cog_load(self) -> None:
        self.bot.add_view(self.service.build_control_view())

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if not self.bot.is_operating_guild(member.guild):
            return
        await self.service.handle_voice_state_update(member, before, after)


@vc_group.command(name="ui", description=messages.UI_DESCRIPTION)
@app_commands.guild_only()
async def vc_ui(interaction: discord.Interaction) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, allow_create_channel=False)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.send_control_message(channel, interaction.user)
    logger.debug(
        f"VCコントローラーUIを送信しました: guild_id={channel.guild.id} "
        f"channel_id={channel.id} user_id={interaction.user.id}"
    )
    await service.send_interaction_message(interaction, messages.UI_SENT)


@vc_group.command(name="name", description=messages.NAME_DESCRIPTION)
@app_commands.rename(vc_name=messages.VC_NAME_LABEL)
@app_commands.describe(vc_name=messages.NEW_VC_NAME_DESCRIPTION)
@app_commands.guild_only()
async def name(interaction: discord.Interaction, vc_name: str) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await interaction.response.defer(thinking=True)
    retry_after = await service.rename_channel_with_rate_limit_handling(channel, interaction.user, vc_name)
    if retry_after is not None:
        await service.send_interaction_message(
            interaction,
            format_rate_limited_error(retry_after, action=messages.NAME_CHANGE_RATE_LIMIT_ACTION),
            ephemeral=True,
        )
        return

    await service.refresh_control_panels(channel)
    logger.debug(
        "VC名を変更しました: command=/vc name "
        f"guild_id={interaction.guild_id} channel_id={channel.id} user_id={interaction.user.id} name={vc_name}"
    )
    await service.send_interaction_message(interaction, messages.vc_name_changed(vc_name=vc_name))


@vc_group.command(name="limit", description=messages.LIMIT_DESCRIPTION)
@app_commands.rename(limit=messages.LIMIT_LABEL)
@app_commands.describe(limit=messages.LIMIT_LABEL)
@app_commands.guild_only()
async def limit(interaction: discord.Interaction, limit: app_commands.Range[int, 0, 99] = 0) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.set_user_limit(channel, interaction.user, limit)
    await service.refresh_control_panels(channel)
    logger.debug(
        "VC人数制限を変更しました: command=/vc limit "
        f"guild_id={interaction.guild_id} channel_id={channel.id} user_id={interaction.user.id} limit={limit}"
    )
    await service.send_interaction_message(interaction, messages.vc_limit_changed(limit=limit))


@vc_group.command(name="block", description=messages.BLOCK_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.BLOCK_USER_DESCRIPTION)
@app_commands.guild_only()
async def block(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await channel.set_permissions(
        user,
        overwrite=blocked_permissions,
        reason=f"[{generate_timestamp()}] {interaction.user.name} がユーザーをブロックしました。",
    )
    if user.voice is not None and user.voice.channel and user.voice.channel.id == channel.id:
        await user.move_to(
            None,
            reason=f"[{generate_timestamp()}] {interaction.user.name} がユーザーをブロックしました。",
        )
    logger.debug(
        f"VCでユーザーをブロックしました: guild_id={channel.guild.id} channel_id={channel.id} "
        f"user_id={interaction.user.id} target_id={user.id}"
    )
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, messages.user_blocked(display_name=user.display_name))


@vc_group.command(name="unblock", description=messages.UNBLOCK_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.UNBLOCK_USER_DESCRIPTION)
@app_commands.guild_only()
async def unblock(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await channel.set_permissions(
        user,
        overwrite=None,
        reason=f"[{generate_timestamp()}] {interaction.user.name} がユーザーをブロック解除しました。",
    )
    logger.debug(
        f"VCのブロックを解除しました: guild_id={channel.guild.id} channel_id={channel.id} "
        f"user_id={interaction.user.id} target_id={user.id}"
    )
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, messages.user_unblocked(display_name=user.display_name))


@vc_group.command(name="op", description=messages.OP_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.OP_USER_DESCRIPTION)
@app_commands.guild_only()
async def op(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await channel.set_permissions(
        user,
        overwrite=owner_permissions,
        reason=f"[{generate_timestamp()}] {interaction.user.name} がユーザーにVC管理権限を付与しました。",
    )
    logger.debug(
        f"VC管理権限を付与しました: guild_id={channel.guild.id} channel_id={channel.id} "
        f"user_id={interaction.user.id} target_id={user.id}"
    )
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, messages.user_opped(display_name=user.display_name))


@vc_group.command(name="deop", description=messages.DEOP_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL)
@app_commands.describe(user=messages.DEOP_USER_DESCRIPTION)
@app_commands.guild_only()
async def deop(interaction: discord.Interaction, user: discord.Member) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await channel.set_permissions(
        user,
        overwrite=None,
        reason=f"[{generate_timestamp()}] {interaction.user.name} がユーザーのVC管理権限を剥奪しました。",
    )
    logger.debug(
        f"VC管理権限を剥奪しました: guild_id={channel.guild.id} channel_id={channel.id} "
        f"user_id={interaction.user.id} target_id={user.id}"
    )
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, messages.user_deopped(display_name=user.display_name))


@vc_group.command(name="private", description=messages.PRIVATE_DESCRIPTION)
@app_commands.guild_only()
async def private(interaction: discord.Interaction) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.set_private(channel, interaction.user, True)
    await service.refresh_control_panels(channel)
    logger.debug(
        "VCを非公開にしました: command=/vc private "
        f"guild_id={interaction.guild_id} channel_id={channel.id} user_id={interaction.user.id}"
    )
    await service.send_interaction_message(
        interaction,
        messages.PRIVATE_COMPLETED,
    )


@vc_group.command(name="public", description=messages.PUBLIC_DESCRIPTION)
@app_commands.guild_only()
async def public(interaction: discord.Interaction) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.set_private(channel, interaction.user, False)
    await service.refresh_control_panels(channel)
    logger.debug(
        "VCを公開しました: command=/vc public "
        f"guild_id={interaction.guild_id} channel_id={channel.id} user_id={interaction.user.id}"
    )
    await service.send_interaction_message(interaction, messages.PUBLIC_COMPLETED)


async def setup(bot: AsteroidBot) -> None:
    get_vc_service(bot)
    register_group(bot, vc_group)
    await bot.add_cog(VoiceCreateCog(bot))

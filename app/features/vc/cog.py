from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from app.common.command_groups import get_bot, register_group
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

from .service import blocked_permissions, get_vc_service, owner_permissions

vc_group = app_commands.Group(name="vc", description="自分の通話を設定するコマンド")


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
        await self.service.handle_voice_state_update(member, before, after)


@vc_group.command(name="ui", description="VCのコントローラーUIを表示")
@app_commands.guild_only()
async def vc_ui(interaction: discord.Interaction) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, allow_create_channel=False)
    if channel is None:
        return

    await service.send_control_message(channel, interaction.user)
    await service.send_interaction_message(interaction, "VCのコントローラーUIを送信しました。")


@vc_group.command(name="name", description="VCの名前を変更")
@app_commands.describe(vc_name="新しく設定するVCの名前")
@app_commands.guild_only()
async def name(interaction: discord.Interaction, vc_name: str) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.rename_channel(channel, interaction.user, vc_name)
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, f"VCの名前を`{vc_name}`に変更しました。")


@vc_group.command(name="limit", description="VCに人数制限を設定")
@app_commands.describe(limit="人数制限")
@app_commands.guild_only()
async def limit(interaction: discord.Interaction, limit: app_commands.Range[int, 0, 99] = 0) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.set_user_limit(channel, interaction.user, limit)
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, f"チャンネルの人数制限を`{limit}`人に設定しました。")


@vc_group.command(name="block", description="VCからユーザーをブロック")
@app_commands.describe(user="VCに接続できなくするユーザー")
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
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, f"`{user.display_name}`をブロックしました！")


@vc_group.command(name="unblock", description="VCからブロックしたユーザーをブロック解除")
@app_commands.describe(user="VCブロックを解除するユーザー")
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
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, f"`{user.display_name}`をブロック解除しました！")


@vc_group.command(name="op", description="VCの管理権限を別のユーザーにも付与")
@app_commands.describe(user="VCの管理権限を与えるユーザー")
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
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, f"`{user.display_name}`にVCの管理権限を与えました！")


@vc_group.command(name="deop", description="VCの管理権限を他のユーザーから剥奪")
@app_commands.describe(user="管理権限を剥奪するユーザー")
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
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, f"`{user.display_name}`からVCの管理権限を剥奪しました！")


@vc_group.command(name="private", description="VCを非公開に設定")
@app_commands.guild_only()
async def private(interaction: discord.Interaction) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.set_private(channel, interaction.user, True)
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(
        interaction,
        "VCを非公開に設定しました。\n管理権限を与えることで他のユーザーがこのVCを見えるようになります。",
    )


@vc_group.command(name="public", description="VCを公開に設定")
@app_commands.guild_only()
async def public(interaction: discord.Interaction) -> None:
    service = get_vc_service(get_bot(interaction))
    channel = await service.ensure_voice_channel(interaction, require_manage=True)
    if channel is None or not isinstance(interaction.user, discord.Member):
        return

    await service.set_private(channel, interaction.user, False)
    await service.refresh_control_panels(channel)
    await service.send_interaction_message(interaction, "VCを公開に設定しました。")


async def setup(bot: AsteroidBot) -> None:
    get_vc_service(bot)
    register_group(bot, vc_group)
    await bot.add_cog(VoiceCreateCog(bot))

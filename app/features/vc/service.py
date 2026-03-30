from __future__ import annotations

import datetime
from logging import getLogger

import discord

from app.common.constants import AsteroidColor
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger(__name__)

owner_permissions = discord.PermissionOverwrite(
    view_channel=True,
    manage_channels=True,
    connect=True,
    send_messages=True,
    manage_messages=True,
    manage_events=True,
)

blocked_permissions = discord.PermissionOverwrite(
    view_channel=False,
    manage_channels=False,
    connect=False,
    send_messages=False,
    manage_messages=False,
    manage_events=False,
)


def build_select_default_values(members: list[discord.Member]) -> list[discord.SelectDefaultValue]:
    return [
        discord.SelectDefaultValue(id=member.id, type=discord.SelectDefaultValueType.user) for member in members[:25]
    ]


class VoiceCreateService:
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.control_panel_messages: dict[int, tuple[int, int]] = {}

    def get_voice_create_channel_id(self) -> int:
        return self.bot.config.vc.voice_create_channel_id

    def get_voice_category_id(self) -> int:
        return self.bot.config.vc.voice_category_id

    def normalize_color(self, color: discord.Color | int | None) -> int:
        if isinstance(color, discord.Color):
            return color.value or AsteroidColor.INFO
        if isinstance(color, int):
            return color or AsteroidColor.INFO
        return AsteroidColor.INFO

    def track_control_message(
        self,
        channel: discord.VoiceChannel,
        message: discord.Message,
        *,
        color: discord.Color | int | None,
    ) -> None:
        self.bot.remember_message(message)
        self.control_panel_messages[channel.id] = (message.id, self.normalize_color(color))

    def untrack_control_message(self, channel_id: int, message_id: int) -> None:
        tracked_message = self.control_panel_messages.get(channel_id)
        if tracked_message is None or tracked_message[0] != message_id:
            return
        self.control_panel_messages.pop(channel_id, None)

    def clear_control_messages(self, channel_id: int) -> None:
        self.control_panel_messages.pop(channel_id, None)

    async def send_interaction_message(
        self,
        interaction: discord.Interaction,
        content: str,
        *,
        ephemeral: bool = False,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
            return
        await interaction.response.send_message(content, ephemeral=ephemeral)

    async def ensure_voice_channel(
        self,
        interaction: discord.Interaction,
        *,
        require_manage: bool = False,
        allow_create_channel: bool = False,
        expected_channel_id: int | None = None,
    ) -> discord.VoiceChannel | None:
        channel: discord.VoiceChannel | None = None
        if interaction.guild is not None and expected_channel_id is not None:
            expected_channel = interaction.guild.get_channel(expected_channel_id)
            if isinstance(expected_channel, discord.VoiceChannel):
                channel = expected_channel

        if channel is None and isinstance(interaction.channel, discord.VoiceChannel):
            channel = interaction.channel

        if channel is None and isinstance(interaction.user, discord.Member):
            voice_channel = interaction.user.voice.channel if interaction.user.voice else None
            if isinstance(voice_channel, discord.VoiceChannel):
                channel = voice_channel

        if channel is None:
            logger.debug(
                f"VC外で操作が呼ばれました: channel_id={interaction.channel_id} user_id={interaction.user.id}"
            )
            await self.send_interaction_message(interaction, "このコマンドはVCチャンネルでのみ使えます。")
            return None

        if not allow_create_channel and channel.id == self.get_voice_create_channel_id():
            logger.debug(
                f"VC作成チャンネルへの操作を拒否しました: guild_id={channel.guild.id} "
                f"channel_id={channel.id} user_id={interaction.user.id}"
            )
            await self.send_interaction_message(interaction, "VC作成用チャンネル自体は操作できません。")
            return None

        if require_manage and not channel.permissions_for(interaction.user).manage_channels:
            logger.debug(
                f"VC管理権限不足で操作を拒否しました: guild_id={channel.guild.id} "
                f"channel_id={channel.id} user_id={interaction.user.id}"
            )
            await self.send_interaction_message(interaction, "VCの管理権限がありません。")
            return None
        return channel

    def get_owner_and_blocked_lists(
        self, channel: discord.VoiceChannel
    ) -> tuple[list[discord.Member], list[discord.Member], str, str]:
        owner_list: list[discord.Member] = []
        blocked_list: list[discord.Member] = []

        for overwrite_target, overwrite in channel.overwrites.items():
            if not isinstance(overwrite_target, discord.Member):
                continue

            if overwrite == owner_permissions:
                owner_list.append(overwrite_target)
            elif overwrite == blocked_permissions:
                blocked_list.append(overwrite_target)

        owner_mentions = " ".join(member.mention for member in owner_list) or "なし"
        blocked_mentions = " ".join(member.mention for member in blocked_list) or "なし"
        return owner_list, blocked_list, owner_mentions, blocked_mentions

    def is_private_channel(self, channel: discord.VoiceChannel) -> bool:
        overwrite = channel.overwrites_for(channel.guild.default_role)
        return overwrite.view_channel is False and overwrite.connect is False

    def build_control_embed(self, channel: discord.VoiceChannel, color: discord.Color | int) -> discord.Embed:
        owner_list, blocked_list, owner_mentions, blocked_mentions = self.get_owner_and_blocked_lists(channel)
        embed = discord.Embed(
            title=channel.name,
            description="`/vc ui`でこのヘルプを再表示できます。",
            color=color or AsteroidColor.INFO,
            timestamp=datetime.datetime.now(),
        )
        embed.add_field(name="ブロックしたユーザー", value=blocked_mentions, inline=False)
        embed.add_field(name="管理権限を与えたユーザー", value=owner_mentions, inline=False)
        embed.set_footer(
            text=(
                f"人数制限: {channel.user_limit or '無制限'}"
                f" | 非公開: {'はい' if self.is_private_channel(channel) else 'いいえ'}"
                f" | ブロック: {len(blocked_list)}人"
                f" | 管理権限: {len(owner_list)}人"
            )
        )
        return embed

    def build_control_view(self, channel: discord.VoiceChannel | None = None) -> discord.ui.View:
        from .views import VoiceControlView

        return VoiceControlView(self, channel)

    async def refresh_control_message(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        *,
        color: discord.Color | int | None = None,
    ) -> None:
        if interaction.message is not None:
            tracked_color = color
            if tracked_color is None and interaction.message.embeds:
                tracked_color = interaction.message.embeds[0].color
            if tracked_color is None:
                tracked_color = interaction.user.color
            self.track_control_message(channel, interaction.message, color=tracked_color)
        await self.refresh_control_panels(channel)

    async def refresh_control_panels(self, channel: discord.VoiceChannel) -> None:
        tracked_message = self.control_panel_messages.get(channel.id)
        if tracked_message is None:
            return

        message_id, color = tracked_message
        message = self.bot.get_message(message_id)
        if message is None:
            self.untrack_control_message(channel.id, message_id)
            return

        try:
            await message.edit(
                embed=self.build_control_embed(channel, color),
                view=self.build_control_view(channel),
            )
        except discord.NotFound, discord.Forbidden:
            logger.debug(f"VCコントロールパネルの追跡を解除しました: channel_id={channel.id} message_id={message_id}")
            self.untrack_control_message(channel.id, message_id)

    async def send_control_message(
        self,
        channel: discord.VoiceChannel,
        member: discord.Member,
        *,
        mention_member: bool = False,
    ) -> discord.Message:
        message = await channel.send(
            content=member.mention if mention_member else None,
            embed=self.build_control_embed(channel, member.color),
            view=self.build_control_view(channel),
        )
        self.track_control_message(channel, message, color=member.color)
        return message

    async def handle_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel is not None and isinstance(before.channel, discord.VoiceChannel):
            if (
                before.channel.category_id == self.get_voice_category_id()
                and before.channel.id != self.get_voice_create_channel_id()
                and len(before.channel.members) == 0
            ):
                self.clear_control_messages(before.channel.id)
                await before.channel.delete(reason=f"[{generate_timestamp()}] 誰もいなくなったため自動削除。")
                logger.debug(
                    f"VCを自動削除しました: guild_id={before.channel.guild.id} channel_id={before.channel.id}"
                )

        if after.channel is None or after.channel.id != self.get_voice_create_channel_id():
            return
        if after.channel.category is None:
            return

        overwrites = dict(after.channel.overwrites)
        overwrites[member] = owner_permissions
        new_channel = await after.channel.category.create_voice_channel(
            name=f"{member.display_name}のVC",
            reason=f"[{generate_timestamp()}] {member.name} がVCを作成しました。",
            overwrites=overwrites,
        )
        await member.move_to(new_channel)
        await self.send_control_message(new_channel, member, mention_member=True)
        logger.debug(
            f"VCを自動作成しました: guild_id={member.guild.id} channel_id={new_channel.id} "
            f"owner_id={member.id} category_id={after.channel.category.id}"
        )

    async def rename_channel(self, channel: discord.VoiceChannel, actor: discord.Member, name: str) -> None:
        await channel.edit(
            name=name[:100],
            reason=f"[{generate_timestamp()}] {actor.name} がチャンネル名を変更しました。",
        )
        logger.debug(f"VC名を変更しました: guild_id={channel.guild.id} channel_id={channel.id} user_id={actor.id}")

    async def set_private(self, channel: discord.VoiceChannel, actor: discord.Member, private: bool) -> None:
        await channel.set_permissions(
            channel.guild.default_role,
            overwrite=blocked_permissions if private else None,
            reason=f"[{generate_timestamp()}] {actor.name} がVCの公開設定を変更しました。",
        )
        logger.debug(
            f"VC公開設定を変更しました: guild_id={channel.guild.id} "
            f"channel_id={channel.id} user_id={actor.id} private={private}"
        )

    async def set_user_limit(self, channel: discord.VoiceChannel, actor: discord.Member, limit: int) -> None:
        clamped_limit = max(0, min(99, limit))
        await channel.edit(
            user_limit=clamped_limit,
            reason=f"[{generate_timestamp()}] {actor.name} が人数制限を変更しました。",
        )
        logger.debug(
            f"VC人数制限を変更しました: guild_id={channel.guild.id} "
            f"channel_id={channel.id} user_id={actor.id} limit={clamped_limit}"
        )

    async def update_blocked_members(
        self,
        channel: discord.VoiceChannel,
        actor: discord.Member,
        selected_members: list[discord.Member],
    ) -> tuple[list[discord.Member], list[discord.Member]]:
        _, blocked_members, _, _ = self.get_owner_and_blocked_lists(channel)
        selected_map = {member.id: member for member in selected_members if member.id != actor.id}

        unblocked_members: list[discord.Member] = []
        newly_blocked_members: list[discord.Member] = []

        for member in blocked_members:
            if member.id in selected_map:
                continue
            await channel.set_permissions(
                member,
                overwrite=None,
                reason=f"[{generate_timestamp()}] {actor.name} がブロックを解除しました。",
            )
            unblocked_members.append(member)

        blocked_ids = {member.id for member in blocked_members}
        for member in selected_map.values():
            if member.id in blocked_ids:
                continue
            await channel.set_permissions(
                member,
                overwrite=blocked_permissions,
                reason=f"[{generate_timestamp()}] {actor.name} がブロックしました。",
            )
            if member.voice is not None and member.voice.channel and member.voice.channel.id == channel.id:
                await member.move_to(None, reason=f"[{generate_timestamp()}] {actor.name} がブロックしました。")
            newly_blocked_members.append(member)

        if newly_blocked_members or unblocked_members:
            logger.debug(
                f"VCブロック対象を更新しました: guild_id={channel.guild.id} channel_id={channel.id} "
                f"user_id={actor.id} blocked_count={len(newly_blocked_members)} "
                f"unblocked_count={len(unblocked_members)}"
            )

        return newly_blocked_members, unblocked_members

    async def update_operator_members(
        self,
        channel: discord.VoiceChannel,
        actor: discord.Member,
        selected_members: list[discord.Member],
    ) -> tuple[list[discord.Member], list[discord.Member]]:
        owner_members, _, _, _ = self.get_owner_and_blocked_lists(channel)
        selected_map = {member.id: member for member in selected_members if member.id != actor.id}

        deoped_members: list[discord.Member] = []
        newly_oped_members: list[discord.Member] = []

        for member in owner_members:
            if member.id == actor.id or member.id in selected_map:
                continue
            await channel.set_permissions(
                member,
                overwrite=None,
                reason=f"[{generate_timestamp()}] {actor.name} が管理権限を剥奪しました。",
            )
            deoped_members.append(member)

        owner_ids = {member.id for member in owner_members}
        for member in selected_map.values():
            if member.id in owner_ids:
                continue
            await channel.set_permissions(
                member,
                overwrite=owner_permissions,
                reason=f"[{generate_timestamp()}] {actor.name} が管理権限を付与しました。",
            )
            newly_oped_members.append(member)

        if newly_oped_members or deoped_members:
            logger.debug(
                f"VC管理権限対象を更新しました: guild_id={channel.guild.id} channel_id={channel.id} "
                f"user_id={actor.id} oped_count={len(newly_oped_members)} "
                f"deoped_count={len(deoped_members)}"
            )

        return newly_oped_members, deoped_members


def get_vc_service(bot: AsteroidBot) -> VoiceCreateService:
    service = bot.services.get("vc")
    if isinstance(service, VoiceCreateService):
        return service

    new_service = VoiceCreateService(bot)
    bot.services["vc"] = new_service
    return new_service

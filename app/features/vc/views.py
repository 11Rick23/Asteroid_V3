from __future__ import annotations

import discord

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView, GuildScopedModal

from .service import VoiceCreateService, build_select_default_values


def member_mentions(members: list[discord.Member]) -> str:
    return " ".join(member.mention for member in members) or "なし"


class NameChangeModal(GuildScopedModal, title="VC名変更"):
    vc_name = discord.ui.TextInput(label="新しいVCの名前", max_length=100)

    def __init__(self, service: VoiceCreateService, channel_id: int | None = None):
        super().__init__(timeout=None)
        self.service = service
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = await self.service.ensure_voice_channel(
            interaction,
            require_manage=True,
            expected_channel_id=self.channel_id,
        )
        if channel is None or not isinstance(interaction.user, discord.Member):
            return

        await self.service.rename_channel(channel, interaction.user, self.vc_name.value)
        await self.service.refresh_control_panels(channel)
        await self.service.send_interaction_message(
            interaction,
            f"`{interaction.user.display_name}`がVCの名前を`{self.vc_name.value}`に変更しました。",
        )


class ChangeNameButton(discord.ui.Button["VoiceControlView"]):
    def __init__(self, service: VoiceCreateService, channel_id: int | None = None):
        super().__init__(
            label="VC名を変更",
            style=discord.ButtonStyle.blurple,
            custom_id="vc_change_name_button",
        )
        self.service = service
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(NameChangeModal(self.service, self.channel_id))


class TogglePrivacyButton(discord.ui.Button["VoiceControlView"]):
    def __init__(self, service: VoiceCreateService, channel: discord.VoiceChannel | None = None):
        is_private = bool(channel and service.is_private_channel(channel))
        label = "公開にする" if is_private else "非公開にする"
        style = discord.ButtonStyle.red if is_private else discord.ButtonStyle.green
        super().__init__(
            label=label,
            style=style,
            custom_id="vc_toggle_private_button",
        )
        self.service = service
        self.channel_id = channel.id if channel else None

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        channel = await self.service.ensure_voice_channel(
            interaction,
            require_manage=True,
            expected_channel_id=self.channel_id,
        )
        if channel is None or not isinstance(interaction.user, discord.Member):
            return

        private = not self.service.is_private_channel(channel)
        await self.service.set_private(channel, interaction.user, private)
        await self.service.refresh_control_message(interaction, channel)
        await interaction.followup.send(
            (
                "VCを非公開に設定しました。\n管理権限を与えることで他のユーザーがこのVCを見えるようになります。"
                if private
                else "VCを公開に設定しました。"
            ),
        )


class UserLimitSelect(discord.ui.Select["VoiceControlView"]):
    def __init__(self, service: VoiceCreateService, channel: discord.VoiceChannel | None = None):
        current_limit = channel.user_limit if channel else 0
        options = [
            discord.SelectOption(label="無制限", value="0", default=current_limit == 0),
            *[
                discord.SelectOption(label=str(number), value=str(number), default=current_limit == number)
                for number in range(1, 16)
            ],
        ]
        super().__init__(
            placeholder="人数制限",
            options=options,
            custom_id="vc_user_limit_select",
            min_values=1,
            max_values=1,
        )
        self.service = service
        self.channel_id = channel.id if channel else None

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        channel = await self.service.ensure_voice_channel(
            interaction,
            require_manage=True,
            expected_channel_id=self.channel_id,
        )
        if channel is None or not isinstance(interaction.user, discord.Member):
            return

        limit = int(self.values[0])
        await self.service.set_user_limit(channel, interaction.user, limit)
        await self.service.refresh_control_message(interaction, channel)
        await interaction.followup.send(
            f"`{interaction.user.display_name}`がVCの人数制限を`{limit}`に変更しました。",
        )


class BlockedUserSelect(discord.ui.UserSelect["VoiceControlView"]):
    def __init__(self, service: VoiceCreateService, channel: discord.VoiceChannel | None = None):
        blocked_members = service.get_owner_and_blocked_lists(channel)[1] if channel else []
        super().__init__(
            custom_id="vc_block_user_select",
            placeholder="VCからブロックするユーザー",
            min_values=0,
            max_values=25,
            default_values=build_select_default_values(blocked_members),
        )
        self.service = service
        self.channel_id = channel.id if channel else None

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        channel = await self.service.ensure_voice_channel(
            interaction,
            require_manage=True,
            expected_channel_id=self.channel_id,
        )
        if channel is None or not isinstance(interaction.user, discord.Member):
            return

        selected_members = [member for member in self.values if isinstance(member, discord.Member)]
        blocked_members, unblocked_members = await self.service.update_blocked_members(
            channel,
            interaction.user,
            selected_members,
        )
        await self.service.refresh_control_message(interaction, channel)
        embed = discord.Embed(
            title="ユーザーをブロックしました。",
            description=(
                f"ブロックしたユーザー:\n{member_mentions(blocked_members)}\n\n"
                f"ブロックを解除したユーザー:\n{member_mentions(unblocked_members)}"
            ),
        )
        await interaction.followup.send(embed=embed)


class OperatorUserSelect(discord.ui.UserSelect["VoiceControlView"]):
    def __init__(self, service: VoiceCreateService, channel: discord.VoiceChannel | None = None):
        owner_members = service.get_owner_and_blocked_lists(channel)[0] if channel else []
        super().__init__(
            custom_id="vc_op_user_select",
            placeholder="管理権限を与えるユーザー",
            min_values=0,
            max_values=25,
            default_values=build_select_default_values(owner_members),
        )
        self.service = service
        self.channel_id = channel.id if channel else None

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        channel = await self.service.ensure_voice_channel(
            interaction,
            require_manage=True,
            expected_channel_id=self.channel_id,
        )
        if channel is None or not isinstance(interaction.user, discord.Member):
            return

        selected_members = [member for member in self.values if isinstance(member, discord.Member)]
        oped_members, deoped_members = await self.service.update_operator_members(
            channel,
            interaction.user,
            selected_members,
        )
        await self.service.refresh_control_message(interaction, channel)
        embed = discord.Embed(
            title="ユーザーに管理権限を与えました。",
            description=(
                f"管理権限を与えたユーザー:\n{member_mentions(oped_members)}\n\n"
                f"管理権限を剥奪したユーザー:\n{member_mentions(deoped_members)}"
            ),
        )
        await interaction.followup.send(embed=embed)


class VoiceControlView(GuildScopedLayoutView):
    def __init__(
        self,
        service: VoiceCreateService,
        channel: discord.VoiceChannel | None = None,
        *,
        color: discord.Color | int | None = None,
    ) -> None:
        super().__init__(timeout=None)
        channel_name = channel.name if channel else "VCコントロール"

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# {channel_name}"),
                discord.ui.ActionRow(
                    ChangeNameButton(service, channel.id if channel else None),
                    TogglePrivacyButton(service, channel),
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay("### 人数制限"),
                discord.ui.ActionRow(UserLimitSelect(service, channel)),
                discord.ui.Separator(),
                discord.ui.TextDisplay("### ブロックしたユーザー"),
                discord.ui.ActionRow(BlockedUserSelect(service, channel)),
                discord.ui.Separator(),
                discord.ui.TextDisplay("### 管理権限を与えたユーザー"),
                discord.ui.ActionRow(OperatorUserSelect(service, channel)),
                accent_color=color or AsteroidColor.INFO,
            )
        )

from __future__ import annotations

from logging import getLogger

import discord

from app.common.guild_scope import GuildScopedView
from app.database.repositories.role_panel import RolePanelCategoryDetail

from .service import (
    PANEL_CATEGORY_LIMIT,
    RolePanelService,
    get_visible_category_roles,
    member_needs_boost,
)

logger = getLogger(__name__)

CATEGORY_BUTTON_LABEL_LIMIT = 80


def _response_embed(title: str, description: str, *, color: int = 0xB2B1B5) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def build_role_select_options(
    category: RolePanelCategoryDetail,
    member: discord.Member,
) -> list[discord.SelectOption]:
    member_role_ids = {role.id for role in member.roles}
    options: list[discord.SelectOption] = []
    for role_data in get_visible_category_roles(category, member.guild):
        role = member.guild.get_role(role_data.role_id)
        if role is None:
            continue
        options.append(
            discord.SelectOption(
                label=role.name[:100],
                value=str(role.id),
                default=role.id in member_role_ids,
            )
        )
    return options


class RolePanelRoleSelect(discord.ui.Select["RolePanelSelectView"]):
    def __init__(
        self,
        service: RolePanelService,
        category: RolePanelCategoryDetail,
        member: discord.Member,
        options: list[discord.SelectOption],
    ):
        super().__init__(
            custom_id=f"rolepanel_select:{category.category_id}:{member.id}",
            placeholder="付与したいロールを選択",
            min_values=0,
            max_values=max(1, len(options)),
            options=options,
        )
        self.service = service
        self.category_id = category.category_id
        self.member_id = member.id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.member_id:
            logger.debug(
                "ロールパネル選択メニューの操作を拒否しました: "
                f"guild_id={interaction.guild_id} actor_id={interaction.user.id} "
                f"owner_id={self.member_id} category_id={self.category_id}"
            )
            await interaction.response.send_message(
                embed=_response_embed("操作できません", "この選択メニューはあなた専用ではありません。"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_role_ids = {int(value) for value in self.values}
        message = await self.service.sync_member_roles(interaction, self.category_id, selected_role_ids)
        await interaction.followup.send(
            embed=_response_embed("ロールを同期しました", message or "ロールを同期しました。"),
            ephemeral=True,
        )


class RolePanelSelectView(GuildScopedView):
    def __init__(
        self,
        service: RolePanelService,
        category: RolePanelCategoryDetail,
        member: discord.Member,
        options: list[discord.SelectOption],
    ):
        super().__init__(timeout=300)
        if options:
            self.add_item(RolePanelRoleSelect(service, category, member, options))


class RolePanelCategoryButton(discord.ui.Button["RolePanelView"]):
    def __init__(self, service: RolePanelService, category: RolePanelCategoryDetail, row: int):
        super().__init__(
            label=category.name[:CATEGORY_BUTTON_LABEL_LIMIT],
            style=discord.ButtonStyle.blurple,
            custom_id=f"rolepanel_category:{category.category_id}",
            row=row,
            disabled=not category.roles,
        )
        self.service = service
        self.category_id = category.category_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            logger.warning(f"ロールパネルカテゴリボタンをサーバー外で受信しました: category_id={self.category_id}")
            await interaction.response.send_message(
                embed=_response_embed("実行できません", "サーバー内でのみ使用できます。"),
                ephemeral=True,
            )
            return

        category = await self.service.get_category(self.category_id)
        if category is None:
            logger.warning(
                "存在しないロールパネルカテゴリボタンが押されました: "
                f"guild_id={interaction.guild.id} actor_id={interaction.user.id} category_id={self.category_id}"
            )
            await interaction.response.send_message(
                embed=_response_embed("カテゴリが見つかりません", "このカテゴリは存在しません。"),
                ephemeral=True,
            )
            return

        if member_needs_boost(interaction.user, category):
            logger.debug(
                "ロールパネルカテゴリの条件不足でUI表示を拒否しました: "
                f"guild_id={interaction.guild.id} actor_id={interaction.user.id} "
                f"category_id={self.category_id} required=boost"
            )
            await interaction.response.send_message(
                embed=_response_embed(
                    "ブースター専用ロールです",
                    "このカテゴリのロールを入手するにはサーバーをブーストする必要があります。",
                ),
                ephemeral=True,
            )
            return

        options = build_role_select_options(category, interaction.user)
        if not options:
            await interaction.response.send_message(
                embed=_response_embed("ロール未設定", "このカテゴリには選択可能なロールが設定されていません。"),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=_response_embed("ロールを選択", f"**{category.name}** のロールを選択してください。"),
            view=RolePanelSelectView(self.service, category, interaction.user, options),
            ephemeral=True,
        )


class RolePanelView(GuildScopedView):
    def __init__(self, service: RolePanelService, categories: list[RolePanelCategoryDetail]):
        super().__init__(timeout=None)
        for index, category in enumerate(categories[:PANEL_CATEGORY_LIMIT]):
            self.add_item(RolePanelCategoryButton(service, category, row=index // 5))

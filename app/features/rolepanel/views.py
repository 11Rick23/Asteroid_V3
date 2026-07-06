from __future__ import annotations

from logging import getLogger

import discord

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView, GuildScopedModal
from app.database.repositories.role_panel import RolePanelCategoryDetail

from .service import RolePanelService, get_visible_category_roles, member_needs_boost

logger = getLogger(__name__)

CATEGORY_BUTTON_LABEL_LIMIT = 80
PANEL_CATEGORY_LIMIT = 9
CHECKBOX_GROUP_OPTION_LIMIT = 10
ROLE_PANEL_ACCENT_COLORS = (
    AsteroidColor.RED,
    AsteroidColor.ORANGE,
    AsteroidColor.YELLOW,
    AsteroidColor.GREEN,
    AsteroidColor.CYAN,
    AsteroidColor.LIGHT_BLUE,
    AsteroidColor.PURPLE,
    AsteroidColor.PINK,
)


def _response_embed(title: str, description: str, *, color: int = 0xB2B1B5) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def build_role_checkbox_options(
    category: RolePanelCategoryDetail,
    member: discord.Member,
) -> list[discord.CheckboxGroupOption]:
    member_role_ids = {role.id for role in member.roles}
    options: list[discord.CheckboxGroupOption] = []
    for role_data in get_visible_category_roles(category, member.guild):
        role = member.guild.get_role(role_data.role_id)
        if role is None:
            continue
        options.append(
            discord.CheckboxGroupOption(
                label=role.name[:100],
                value=str(role.id),
                default=role.id in member_role_ids,
            )
        )
    return options


class RolePanelRoleModal(GuildScopedModal):
    def __init__(
        self,
        service: RolePanelService,
        category: RolePanelCategoryDetail,
        member: discord.Member,
        options: list[discord.CheckboxGroupOption],
    ) -> None:
        super().__init__(
            title=f"{category.name[:35]} のロール選択",
            custom_id=f"rolepanel_roles:{category.category_id}:{member.id}",
            timeout=300,
        )
        self.service = service
        self.category_id = category.category_id
        self.member_id = member.id
        self.checkbox_groups: list[discord.ui.CheckboxGroup[RolePanelRoleModal]] = []

        for index in range(0, len(options), CHECKBOX_GROUP_OPTION_LIMIT):
            chunk = options[index : index + CHECKBOX_GROUP_OPTION_LIMIT]
            group = discord.ui.CheckboxGroup[RolePanelRoleModal](
                custom_id=f"rolepanel_roles:{category.category_id}:{member.id}:{index // CHECKBOX_GROUP_OPTION_LIMIT}",
                required=False,
                min_values=0,
                max_values=len(chunk),
                options=chunk,
            )
            self.checkbox_groups.append(group)
            self.add_item(discord.ui.Label(text="\u200b", component=group))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        if interaction.user.id == self.member_id:
            return True
        logger.debug(
            "ロールパネル選択Modalの操作を拒否しました: "
            f"guild_id={interaction.guild_id} actor_id={interaction.user.id} "
            f"owner_id={self.member_id} category_id={self.category_id}"
        )
        await interaction.response.send_message(
            embed=_response_embed("操作できません", "このロール選択画面はあなた専用です。"),
            ephemeral=True,
        )
        return False

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_role_ids = {int(value) for checkbox_group in self.checkbox_groups for value in checkbox_group.values}
        message = await self.service.sync_member_roles(interaction, self.category_id, selected_role_ids)
        await interaction.followup.send(
            embed=_response_embed("ロールを同期しました", message or "ロールを同期しました。"),
            ephemeral=True,
        )


class RolePanelBoostRequiredModal(GuildScopedModal):
    def __init__(self) -> None:
        super().__init__(title="ブースター専用ロール", timeout=300)
        self.add_item(
            discord.ui.TextDisplay("このカテゴリのロールを入手するにはサーバーをブーストする必要があります。")
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)


class RolePanelCategoryButton(discord.ui.Button["RolePanelView"]):
    def __init__(self, service: RolePanelService, category: RolePanelCategoryDetail):
        super().__init__(
            label="ロールを選択"[:CATEGORY_BUTTON_LABEL_LIMIT],
            style=discord.ButtonStyle.secondary,
            custom_id=f"rolepanel_category:{category.category_id}",
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
            await interaction.response.send_modal(RolePanelBoostRequiredModal())
            return

        options = build_role_checkbox_options(category, interaction.user)
        if not options:
            await interaction.response.send_message(
                embed=_response_embed("ロール未設定", "このカテゴリには選択可能なロールが設定されていません。"),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(RolePanelRoleModal(self.service, category, interaction.user, options))


class RolePanelView(GuildScopedLayoutView):
    def __init__(self, service: RolePanelService, categories: list[RolePanelCategoryDetail]):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.TextDisplay(
                "# 🎭 ロールパネル\nカテゴリごとのボタンから、付け外ししたいロールを選択してください。"
            )
        )

        if not categories:
            self.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay("### カテゴリ未設定\n管理者がカテゴリを追加するまで利用できません。"),
                    accent_color=AsteroidColor.GRAY,
                )
            )
            return

        for index, category in enumerate(categories[:PANEL_CATEGORY_LIMIT]):
            description = category.description or "説明未設定"
            if category.requires_boost:
                description = f"{description}\n\n-# サーバーブースター限定"
            self.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(f"### {category.name}\n{description}"),
                    discord.ui.ActionRow(RolePanelCategoryButton(service, category)),
                    accent_color=ROLE_PANEL_ACCENT_COLORS[index % len(ROLE_PANEL_ACCENT_COLORS)],
                )
            )

        if len(categories) > PANEL_CATEGORY_LIMIT:
            self.add_item(discord.ui.TextDisplay(f"-# 表示対象は先頭{PANEL_CATEGORY_LIMIT}カテゴリです。"))

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger

import discord

from app.common.constants import AsteroidColor
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot
from app.database.repositories.role_panel import RolePanelCategoryDetail, RolePanelRoleData

logger = getLogger(__name__)

ROLE_SELECT_LIMIT = 25


@dataclass(slots=True)
class RoleSyncPlan:
    add_roles: list[discord.Role]
    remove_roles: list[discord.Role]
    ignored_role_ids: set[int]
    unmanageable_role_ids: set[int]


def get_rolepanel_service(bot: AsteroidBot) -> RolePanelService:
    service = bot.services.get("rolepanel")
    if isinstance(service, RolePanelService):
        return service
    service = RolePanelService(bot)
    bot.services["rolepanel"] = service
    return service


def member_needs_boost(member: discord.Member, category: RolePanelCategoryDetail) -> bool:
    if not category.requires_boost:
        return False
    return member.guild.premium_subscriber_role not in member.roles


def role_is_manageable(guild: discord.Guild, role: discord.Role) -> bool:
    return guild.me is not None and role != guild.default_role and not role.managed and role < guild.me.top_role


def sort_roles_by_hierarchy(
    roles: list[RolePanelRoleData],
    guild: discord.Guild | None,
) -> list[RolePanelRoleData]:
    if guild is None:
        return roles

    def sort_key(item: tuple[int, RolePanelRoleData]) -> tuple[int, int]:
        index, role_data = item
        guild_role = guild.get_role(role_data.role_id)
        position = guild_role.position if guild_role is not None else -1
        return -position, index

    indexed_roles = list(enumerate(roles))
    return [role_data for _, role_data in sorted(indexed_roles, key=sort_key)]


def build_role_sync_plan(
    member: discord.Member,
    category: RolePanelCategoryDetail,
    selected_role_ids: set[int],
) -> RoleSyncPlan:
    category_role_ids = {role_data.role_id for role_data in category.roles[:ROLE_SELECT_LIMIT]}
    member_role_ids = {role.id for role in member.roles}
    ignored_role_ids = selected_role_ids - category_role_ids

    add_roles: list[discord.Role] = []
    remove_roles: list[discord.Role] = []
    unmanageable_role_ids: set[int] = set()
    for role_id in category_role_ids:
        role = member.guild.get_role(role_id)
        if role is None:
            continue
        if not role_is_manageable(member.guild, role):
            unmanageable_role_ids.add(role_id)
            continue
        if role_id in selected_role_ids and role_id not in member_role_ids:
            add_roles.append(role)
        elif role_id not in selected_role_ids and role_id in member_role_ids:
            remove_roles.append(role)

    return RoleSyncPlan(
        add_roles=add_roles,
        remove_roles=remove_roles,
        ignored_role_ids=ignored_role_ids,
        unmanageable_role_ids=unmanageable_role_ids,
    )


class RolePanelService:
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def get_categories(self) -> list[RolePanelCategoryDetail]:
        return await self.bot.db.role_panel.get_categories()

    async def get_category(self, category_id: int) -> RolePanelCategoryDetail | None:
        return await self.bot.db.role_panel.get_category(category_id)

    def build_panel_embed(
        self,
        categories: list[RolePanelCategoryDetail],
        guild: discord.Guild | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="ロールパネル",
            description="カテゴリを選択して、付け外ししたいロールを選んでください。",
            color=AsteroidColor.GREEN,
        )
        if not categories:
            embed.add_field(
                name="カテゴリ未設定",
                value="管理者がカテゴリを追加するまで利用できません。",
                inline=False,
            )
            return embed

        for category in categories:
            category_roles = sort_roles_by_hierarchy(category.roles, guild)
            role_mentions = (
                "\n".join(f"<@&{role.role_id}>" for role in category_roles[:ROLE_SELECT_LIMIT]) or "ロール未設定"
            )
            description = ""
            if len(category.roles) > ROLE_SELECT_LIMIT:
                description += f"表示対象は先頭{ROLE_SELECT_LIMIT}件です。\n"
            embed.add_field(
                name=category.name,
                value=f"{description}{role_mentions}",
                inline=True,
            )
        return embed

    async def sync_member_roles(
        self,
        interaction: discord.Interaction,
        category_id: int,
        selected_role_ids: set[int],
    ) -> str | None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            logger.warning(f"ロールパネル選択をサーバー外で受信しました: category_id={category_id}")
            return "サーバー内でのみ使用できます。"

        category = await self.get_category(category_id)
        if category is None:
            logger.warning(
                "存在しないロールパネルカテゴリが選択されました: "
                f"guild_id={interaction.guild.id} actor_id={interaction.user.id} category_id={category_id}"
            )
            return "このカテゴリは存在しません。"

        if member_needs_boost(interaction.user, category):
            logger.warning(
                "ロールパネルカテゴリの条件不足で拒否しました: "
                f"guild_id={interaction.guild.id} actor_id={interaction.user.id} "
                f"category_id={category_id} required=boost"
            )
            return "このカテゴリを利用するにはサーバーをブーストする必要があります。"

        plan = build_role_sync_plan(interaction.user, category, selected_role_ids)
        reason = f"[{generate_timestamp()}] ロールパネルにより同期されました。"
        if plan.add_roles:
            await interaction.user.add_roles(*plan.add_roles, reason=reason, atomic=False)
        if plan.remove_roles:
            await interaction.user.remove_roles(*plan.remove_roles, reason=reason, atomic=False)

        if plan.ignored_role_ids:
            logger.warning(
                "ロールパネルカテゴリ外ロールの選択を無視しました: "
                f"guild_id={interaction.guild.id} actor_id={interaction.user.id} "
                f"category_id={category_id} ignored_role_ids={sorted(plan.ignored_role_ids)}"
            )
        if plan.unmanageable_role_ids:
            logger.warning(
                "ロールパネルで管理不能ロールをスキップしました: "
                f"guild_id={interaction.guild.id} actor_id={interaction.user.id} "
                f"category_id={category_id} role_ids={sorted(plan.unmanageable_role_ids)}"
            )

        logger.debug(
            "ロールパネルでロールを同期しました: "
            f"guild_id={interaction.guild.id} actor_id={interaction.user.id} category_id={category_id} "
            f"add_role_ids={[role.id for role in plan.add_roles]} "
            f"remove_role_ids={[role.id for role in plan.remove_roles]}"
        )
        messages = ["ロールを同期しました。"]
        if plan.add_roles:
            messages.append("追加: " + ", ".join(role.mention for role in plan.add_roles))
        if plan.remove_roles:
            messages.append("削除: " + ", ".join(role.mention for role in plan.remove_roles))
        if plan.unmanageable_role_ids:
            messages.append("一部のロールはBOTの権限またはロール順により操作できませんでした。")
        return "\n".join(messages)

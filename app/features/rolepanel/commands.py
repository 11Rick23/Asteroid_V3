from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.core.bot import AsteroidBot

from . import messages
from .admin_views import RolePanelAdminRoleEditView, RolePanelAdminRoleSelect, response_embed
from .runtime import get_rolepanel_cog, refresh_panel_if_loaded
from .service import CATEGORY_SETTINGS_EMBED_BATCH_LIMIT, get_rolepanel_service

logger = getLogger(__name__)

rolepanel_group = app_commands.Group(
    name="rolepanel",
    description=messages.GROUP_DESCRIPTION,
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)
category_group = app_commands.Group(
    name="category", description=messages.CATEGORY_GROUP_DESCRIPTION, parent=rolepanel_group
)


async def category_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    categories = await get_bot(interaction).db.role_panel.get_categories()
    current = current.lower()
    choices: list[app_commands.Choice[int]] = []
    for category in categories:
        if current and current not in category.name.lower() and current not in str(category.category_id):
            continue
        choices.append(app_commands.Choice(name=category.name[:100], value=category.category_id))
        if len(choices) >= 25:
            break
    return choices


@category_group.command(name="add", description=messages.CATEGORY_ADD_DESCRIPTION)
@app_commands.rename(
    name=messages.CATEGORY_NAME_LABEL, description=messages.DESCRIPTION_LABEL, order=messages.ORDER_LABEL
)
@app_commands.describe(
    name=messages.ADD_CATEGORY_NAME_DESCRIPTION,
    description=messages.ADD_CATEGORY_DESCRIPTION_DESCRIPTION,
    order=messages.ADD_CATEGORY_ORDER_DESCRIPTION,
)
@admin_only
async def category_add(
    interaction: discord.Interaction,
    name: app_commands.Range[str, 1, 100],
    description: app_commands.Range[str, 1, 1000],
    order: app_commands.Range[int, 0] = 0,
) -> None:
    bot = get_bot(interaction)
    category = await bot.db.role_panel.create_category(name, description, order)
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを追加しました: command=/rolepanel category add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category.category_id} name={name} description_length={len(description)} order={order}"
    )
    copy = messages.category_added(category_name=category.name)
    await interaction.response.send_message(embed=response_embed(copy.title, copy.description))


@category_group.command(name="edit", description=messages.CATEGORY_EDIT_DESCRIPTION)
@app_commands.rename(
    category=messages.CATEGORY_LABEL,
    name=messages.CATEGORY_NAME_LABEL,
    description=messages.DESCRIPTION_LABEL,
    order=messages.ORDER_LABEL,
)
@app_commands.describe(
    category=messages.EDIT_CATEGORY_DESCRIPTION,
    name=messages.EDIT_CATEGORY_NAME_DESCRIPTION,
    description=messages.EDIT_CATEGORY_DESCRIPTION_DESCRIPTION,
    order=messages.EDIT_CATEGORY_ORDER_DESCRIPTION,
)
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def category_edit(
    interaction: discord.Interaction,
    category: int,
    name: app_commands.Range[str, 1, 100] | None = None,
    description: app_commands.Range[str, 1, 1000] | None = None,
    order: app_commands.Range[int, 0] | None = None,
) -> None:
    if name is None and description is None and order is None:
        await interaction.response.send_message(
            embed=response_embed(messages.CATEGORY_NO_CHANGES.title, messages.CATEGORY_NO_CHANGES.description),
            ephemeral=True,
        )
        return
    bot = get_bot(interaction)
    updated = await bot.db.role_panel.update_category(
        category,
        name=name,
        description=description,
        display_order=order,
    )
    if updated is None:
        await interaction.response.send_message(
            embed=response_embed(messages.CATEGORY_NOT_FOUND.title, messages.CATEGORY_NOT_FOUND.description),
            ephemeral=True,
        )
        return
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを編集しました: command=/rolepanel category edit "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category} name={name} description_updated={description is not None} order={order}"
    )
    copy = messages.category_updated(category_name=updated.name)
    await interaction.response.send_message(embed=response_embed(copy.title, copy.description))


@category_group.command(name="remove", description=messages.CATEGORY_REMOVE_DESCRIPTION)
@app_commands.rename(category=messages.CATEGORY_LABEL)
@app_commands.describe(category=messages.REMOVE_CATEGORY_DESCRIPTION)
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def category_remove(interaction: discord.Interaction, category: int) -> None:
    bot = get_bot(interaction)
    if not await bot.db.role_panel.delete_category(category):
        await interaction.response.send_message(
            embed=response_embed(messages.CATEGORY_NOT_FOUND.title, messages.CATEGORY_NOT_FOUND.description),
            ephemeral=True,
        )
        return
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを削除しました: command=/rolepanel category remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category}"
    )
    await interaction.response.send_message(
        embed=response_embed(messages.CATEGORY_REMOVED.title, messages.CATEGORY_REMOVED.description)
    )


@rolepanel_group.command(name="edit_role", description=messages.EDIT_ROLE_DESCRIPTION)
@app_commands.rename(category=messages.CATEGORY_LABEL)
@app_commands.describe(category=messages.EDIT_ROLE_CATEGORY_DESCRIPTION)
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def role_edit(interaction: discord.Interaction, category: int) -> None:
    bot = get_bot(interaction)
    category_data = await bot.db.role_panel.get_category(category)
    if category_data is None:
        await interaction.response.send_message(
            embed=response_embed(messages.CATEGORY_NOT_FOUND.title, messages.CATEGORY_NOT_FOUND.description),
            ephemeral=True,
        )
        return
    logger.info(
        "ロールパネルカテゴリのロール編集を開始しました: command=/rolepanel edit_role "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category}"
    )
    role_ids = [role.role_id for role in category_data.roles]
    copy = messages.role_edit_prompt(category_name=category_data.name)
    await interaction.response.send_message(
        embed=response_embed(copy.title, copy.description),
        view=RolePanelAdminRoleEditView(
            RolePanelAdminRoleSelect(
                category,
                role_ids,
                interaction.user.id,
                lambda: refresh_panel_if_loaded(bot),
            )
        ),
        ephemeral=True,
    )


@rolepanel_group.command(name="require_boost", description=messages.REQUIRE_BOOST_DESCRIPTION)
@app_commands.rename(category=messages.CATEGORY_LABEL, required=messages.BOOST_REQUIRED_LABEL)
@app_commands.describe(
    category=messages.REQUIRE_BOOST_CATEGORY_DESCRIPTION,
    required=messages.REQUIRE_BOOST_VALUE_DESCRIPTION,
)
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def required_edit(interaction: discord.Interaction, category: int, required: bool) -> None:
    bot = get_bot(interaction)
    updated = await bot.db.role_panel.update_category(category, requires_boost=required)
    if updated is None:
        await interaction.response.send_message(
            embed=response_embed(messages.CATEGORY_NOT_FOUND.title, messages.CATEGORY_NOT_FOUND.description),
            ephemeral=True,
        )
        return
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリのブースト必須条件を更新しました: command=/rolepanel edit_required_role "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category} required={required}"
    )
    copy = messages.boost_requirement_updated(category_name=updated.name, required=required)
    await interaction.response.send_message(
        embed=response_embed(copy.title, copy.description),
        ephemeral=True,
    )


@rolepanel_group.command(name="refresh", description=messages.REFRESH_DESCRIPTION)
@admin_only
async def refresh(interaction: discord.Interaction) -> None:
    cog = get_rolepanel_cog(get_bot(interaction))
    refreshed = await cog.send_or_update_role_panel() if cog is not None else False
    logger.info(
        "ロールパネルの再描画を実行しました: command=/rolepanel refresh "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"refreshed={refreshed}"
    )
    copy = messages.refresh_result(refreshed=refreshed)
    await interaction.response.send_message(
        embed=response_embed(copy.title, copy.description),
        ephemeral=True,
    )


@rolepanel_group.command(name="list", description=messages.LIST_DESCRIPTION)
@admin_only
async def list_categories(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    categories = await bot.db.role_panel.get_categories()
    embeds = get_rolepanel_service(bot).build_category_settings_embeds(categories)
    logger.info(
        "ロールパネル設定を一覧表示しました: command=/rolepanel list "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_count={len(categories)}"
    )
    await interaction.response.send_message(
        embeds=embeds[:CATEGORY_SETTINGS_EMBED_BATCH_LIMIT],
    )
    for start in range(CATEGORY_SETTINGS_EMBED_BATCH_LIMIT, len(embeds), CATEGORY_SETTINGS_EMBED_BATCH_LIMIT):
        await interaction.followup.send(
            embeds=embeds[start : start + CATEGORY_SETTINGS_EMBED_BATCH_LIMIT],
        )


def register_rolepanel_commands(bot: AsteroidBot) -> None:
    from app.common.command_groups import register_group

    register_group(bot, rolepanel_group)

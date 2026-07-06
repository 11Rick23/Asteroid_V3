from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.core.bot import AsteroidBot

from .admin_views import RolePanelAdminRoleEditView, RolePanelAdminRoleSelect, response_embed
from .runtime import get_rolepanel_cog, refresh_panel_if_loaded
from .service import get_rolepanel_service

logger = getLogger(__name__)

rolepanel_group = app_commands.Group(
    name="rolepanel",
    description="ロールパネル管理コマンド",
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)
category_group = app_commands.Group(name="category", description="カテゴリ管理", parent=rolepanel_group)


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


@category_group.command(name="add", description="ロールパネルカテゴリを追加します")
@app_commands.rename(name="カテゴリ名", description="説明文", order="表示順")
@app_commands.describe(
    name="追加するカテゴリ名",
    description="パネルに表示するカテゴリの説明文",
    order="カテゴリの表示順。小さい値ほど先に表示されます",
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
    await interaction.response.send_message(
        embed=response_embed("カテゴリを追加しました", f"カテゴリ `{category.name}` を追加しました。")
    )


@category_group.command(name="edit", description="ロールパネルカテゴリを編集します")
@app_commands.rename(category="カテゴリ", name="カテゴリ名", description="説明文", order="表示順")
@app_commands.describe(
    category="編集するカテゴリ",
    name="変更後のカテゴリ名",
    description="パネルに表示する変更後の説明文",
    order="変更後の表示順。小さい値ほど先に表示されます",
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
            embed=response_embed("変更内容がありません", "変更内容を1つ以上指定してください。"),
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
            embed=response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを編集しました: command=/rolepanel category edit "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category} name={name} description_updated={description is not None} order={order}"
    )
    await interaction.response.send_message(
        embed=response_embed("カテゴリを更新しました", f"カテゴリ `{updated.name}` を更新しました。")
    )


@category_group.command(name="remove", description="ロールパネルカテゴリを削除します")
@app_commands.rename(category="カテゴリ")
@app_commands.describe(category="削除するカテゴリ")
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def category_remove(interaction: discord.Interaction, category: int) -> None:
    bot = get_bot(interaction)
    if not await bot.db.role_panel.delete_category(category):
        await interaction.response.send_message(
            embed=response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを削除しました: command=/rolepanel category remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category}"
    )
    await interaction.response.send_message(embed=response_embed("カテゴリを削除しました", "カテゴリを削除しました。"))


@rolepanel_group.command(name="edit_role", description="カテゴリ内ロールを編集します")
@app_commands.rename(category="カテゴリ")
@app_commands.describe(category="ロールを編集するカテゴリ")
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def role_edit(interaction: discord.Interaction, category: int) -> None:
    bot = get_bot(interaction)
    category_data = await bot.db.role_panel.get_category(category)
    if category_data is None:
        await interaction.response.send_message(
            embed=response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return
    logger.info(
        "ロールパネルカテゴリのロール編集を開始しました: command=/rolepanel edit_role "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category}"
    )
    role_ids = [role.role_id for role in category_data.roles]
    await interaction.response.send_message(
        embed=response_embed("ロールを編集", f"`{category_data.name}` に表示するロールを選択してください。"),
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


@rolepanel_group.command(name="require_boost", description="カテゴリのロールをブースター限定設定を変更します。")
@app_commands.rename(category="カテゴリ", required="ブースター限定")
@app_commands.describe(category="設定を変更するカテゴリ", required="ブースター限定にするかどうか")
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def required_edit(interaction: discord.Interaction, category: int, required: bool) -> None:
    bot = get_bot(interaction)
    updated = await bot.db.role_panel.update_category(category, requires_boost=required)
    if updated is None:
        await interaction.response.send_message(
            embed=response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return
    await refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリのブースト必須条件を更新しました: command=/rolepanel edit_required_role "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category} required={required}"
    )
    await interaction.response.send_message(
        embed=response_embed(
            "ブースター限定設定を更新しました",
            f"`{updated.name}` のブースター限定設定を {'有効' if required else '無効'} にしました。",
        ),
        ephemeral=True,
    )


@rolepanel_group.command(name="refresh", description="ロールパネルを再描画します")
@admin_only
async def refresh(interaction: discord.Interaction) -> None:
    cog = get_rolepanel_cog(get_bot(interaction))
    refreshed = await cog.send_or_update_role_panel() if cog is not None else False
    logger.info(
        "ロールパネルの再描画を実行しました: command=/rolepanel refresh "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"refreshed={refreshed}"
    )
    await interaction.response.send_message(
        embed=response_embed(
            "ロールパネルを再描画しました" if refreshed else "ロールパネルを再描画できませんでした",
            "ロールパネルを再描画しました。" if refreshed else "ロールパネルを再描画できませんでした。",
        ),
        ephemeral=True,
    )


@rolepanel_group.command(name="list", description="ロールパネル設定を一覧表示します")
@admin_only
async def list_categories(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    categories = await bot.db.role_panel.get_categories()
    embed = get_rolepanel_service(bot).build_panel_embed(categories, interaction.guild)
    logger.info(
        "ロールパネル設定を一覧表示しました: command=/rolepanel list "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_count={len(categories)}"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


def register_rolepanel_commands(bot: AsteroidBot) -> None:
    from app.common.command_groups import register_group

    register_group(bot, rolepanel_group)

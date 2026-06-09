from __future__ import annotations

from collections.abc import Awaitable, Callable
from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app.common.command_groups import get_bot, register_group
from app.common.discord_types import as_member, as_messageable
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.core.bot import AsteroidBot

from .service import ROLE_SELECT_LIMIT, get_rolepanel_service, role_is_manageable
from .views import RolePanelView

logger = getLogger(__name__)

rolepanel_group = app_commands.Group(
    name="rolepanel",
    description="ロールパネル管理コマンド",
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)
category_group = app_commands.Group(name="category", description="カテゴリ管理", parent=rolepanel_group)

PanelRefreshCallback = Callable[[], Awaitable[None]]


def _response_embed(title: str, description: str, *, color: int = 0xB2B1B5) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def _get_rolepanel_cog(bot: AsteroidBot) -> RolePanelCog | None:
    cog = bot.get_cog("RolePanelCog")
    return cog if isinstance(cog, RolePanelCog) else None


class RolePanelCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.service = get_rolepanel_service(bot)
        self.role_panel_message: discord.Message | None = None
        self.initialize_role_panel.start()

    async def cog_unload(self) -> None:
        self.initialize_role_panel.cancel()

    async def cleanup_on_shutdown(self) -> None:
        await self._cleanup_role_panel_message()

    @tasks.loop(count=1)
    async def initialize_role_panel(self) -> None:
        if not self.bot.db.is_initialized():
            return
        await self.send_or_update_role_panel()

    @initialize_role_panel.before_loop
    async def before_initialize_role_panel(self) -> None:
        await self.bot.wait_until_ready()

    @initialize_role_panel.after_loop
    async def cleanup_role_panel_after_loop(self) -> None:
        if self.initialize_role_panel.is_being_cancelled():
            await self._cleanup_role_panel_message()

    async def send_or_update_role_panel(self) -> bool:
        channel_id = self.bot.config.rolepanel.panel_channel_id
        channel = as_messageable(self.bot.get_channel(channel_id))
        if channel is None:
            logger.warning(f"ロールパネル送信先チャンネルが見つかりませんでした: channel_id={channel_id}")
            return False

        categories = await self.service.get_categories()
        guild = channel.guild if isinstance(channel, discord.abc.GuildChannel) else None
        embed = self.service.build_panel_embed(categories, guild)
        view = RolePanelView(self.service, categories)
        if self.role_panel_message is None:
            try:
                self.role_panel_message = await channel.send(embed=embed, view=view)
            except discord.HTTPException:
                logger.exception(f"ロールパネルの初期化に失敗しました: channel_id={channel_id}")
                return False
            logger.info(
                f"ロールパネルを初期化しました: channel_id={channel_id} "
                f"message_id={self.role_panel_message.id}"
            )
            return True

        try:
            await self.role_panel_message.edit(embed=embed, view=view)
        except discord.NotFound:
            logger.info(
                f"ロールパネルメッセージが見つからなかったため再作成します: message_id={self.role_panel_message.id}"
            )
            try:
                self.role_panel_message = await channel.send(embed=embed, view=view)
            except discord.HTTPException:
                logger.exception(f"ロールパネルの再作成に失敗しました: channel_id={channel_id}")
                return False
            logger.info(
                f"ロールパネルを再作成しました: channel_id={channel_id} "
                f"message_id={self.role_panel_message.id}"
            )
        except discord.HTTPException as error:
            logger.warning(
                "ロールパネルの更新に失敗しました。次回の編集または手動更新で再試行します: "
                f"message_id={self.role_panel_message.id} status={error.status} code={error.code}"
            )
            return False
        logger.debug(f"ロールパネルを更新しました: message_id={self.role_panel_message.id}")
        return True

    async def _cleanup_role_panel_message(self) -> None:
        if self.role_panel_message is None:
            return
        try:
            await self.role_panel_message.delete()
            logger.info(f"ロールパネルメッセージを削除しました: message_id={self.role_panel_message.id}")
        except discord.HTTPException:
            pass
        finally:
            self.role_panel_message = None


async def _refresh_panel_if_loaded(bot: AsteroidBot) -> None:
    cog = _get_rolepanel_cog(bot)
    if cog is not None:
        try:
            await cog.send_or_update_role_panel()
        except Exception:
            logger.exception("ロールパネルの再描画中に予期しないエラーが発生しました。")


def _role_manage_error(guild: discord.Guild | None, role: discord.Role) -> str | None:
    if guild is None:
        return "サーバー内で実行してください。"
    if role == guild.default_role:
        return "@everyone はロールパネルに登録できません。"
    if role.managed:
        return "BOTや外部連携により管理されているロールは登録できません。"
    if not role_is_manageable(guild, role):
        return "このロールはBOTから操作できません。BOTのロール順と権限を確認してください。"
    return None


def _role_default_values(role_ids: list[int]) -> list[discord.SelectDefaultValue]:
    return [
        discord.SelectDefaultValue(id=role_id, type=discord.SelectDefaultValueType.role)
        for role_id in role_ids[:ROLE_SELECT_LIMIT]
    ]


async def category_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    bot = get_bot(interaction)
    categories = await bot.db.role_panel.get_categories()
    current = current.lower()
    choices: list[app_commands.Choice[int]] = []
    for category in categories:
        if current and current not in category.name.lower() and current not in str(category.category_id):
            continue
        choices.append(
            app_commands.Choice(
                name=category.name[:100],
                value=category.category_id,
            )
        )
        if len(choices) >= 25:
            break
    return choices


class RolePanelAdminRoleSelect(discord.ui.RoleSelect["RolePanelAdminRoleEditView"]):
    def __init__(
        self,
        category_id: int,
        role_ids: list[int],
        actor_id: int,
        on_update: PanelRefreshCallback,
    ):
        super().__init__(
            custom_id=f"rolepanel_admin_roles:{category_id}:{actor_id}",
            placeholder="カテゴリに表示するロールを選択",
            min_values=0,
            max_values=ROLE_SELECT_LIMIT,
            default_values=_role_default_values(role_ids),
        )
        self.category_id = category_id
        self.actor_id = actor_id
        self.on_update = on_update

    async def callback(self, interaction: discord.Interaction) -> None:
        actor = as_member(interaction.user)
        if interaction.user.id != self.actor_id and actor is None:
            await interaction.response.send_message(
                embed=_response_embed("権限がありません", "この操作を実行する権限がありません。"),
                ephemeral=True,
            )
            return
        if interaction.user.id != self.actor_id and (actor is None or not actor.guild_permissions.administrator):
            logger.warning(
                "ロールパネル編集UIの操作を拒否しました: "
                f"guild_id={interaction.guild_id} actor_id={interaction.user.id} owner_id={self.actor_id} "
                f"category_id={self.category_id}"
            )
            await interaction.response.send_message(
                embed=_response_embed("権限がありません", "この操作を実行する権限がありません。"),
                ephemeral=True,
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=_response_embed("実行できません", "サーバー内で実行してください。"),
                ephemeral=True,
            )
            return

        rejected_roles: list[discord.Role] = []
        role_ids: list[int] = []
        for role in self.values:
            manage_error = _role_manage_error(interaction.guild, role)
            if manage_error is not None:
                rejected_roles.append(role)
                continue
            role_ids.append(role.id)

        bot = get_bot(interaction)
        updated = await bot.db.role_panel.set_roles(self.category_id, role_ids)
        if updated is None:
            await interaction.response.send_message(
                embed=_response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.on_update()
        rejected_role_ids = [role.id for role in rejected_roles]
        logger.info(
            "ロールパネルカテゴリのロールを同期しました: command=/rolepanel edit_role "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
            f"category_id={self.category_id} role_ids={role_ids} rejected_role_ids={rejected_role_ids}"
        )
        message = f"カテゴリのロールを `{len(role_ids)}` 件に更新しました。"
        if rejected_roles:
            message += "\n次のロールはBOTから操作できないため除外しました: " + ", ".join(
                role.mention for role in rejected_roles
            )
        await interaction.followup.send(
            embed=_response_embed("ロールを更新しました", message),
            ephemeral=True,
        )


class RolePanelAdminRoleEditView(discord.ui.View):
    def __init__(
        self,
        item: discord.ui.Item,
    ):
        super().__init__(timeout=300)
        self.add_item(item)


@category_group.command(name="add", description="ロールパネルカテゴリを追加します")
@app_commands.rename(name="カテゴリ名", order="表示順")
@app_commands.describe(name="追加するカテゴリ名", order="カテゴリの表示順。小さい値ほど先に表示されます")
@admin_only
async def category_add(
    interaction: discord.Interaction,
    name: app_commands.Range[str, 1, 100],
    order: app_commands.Range[int, 0] = 0,
) -> None:
    bot = get_bot(interaction)
    category = await bot.db.role_panel.create_category(name, None, order)
    await _refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを追加しました: command=/rolepanel category add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category.category_id} name={name} order={order}"
    )
    await interaction.response.send_message(
        embed=_response_embed("カテゴリを追加しました", f"カテゴリ `{category.name}` を追加しました。")
    )


@category_group.command(name="edit", description="ロールパネルカテゴリを編集します")
@app_commands.rename(category="カテゴリ", name="カテゴリ名", order="表示順")
@app_commands.describe(
    category="編集するカテゴリ",
    name="変更後のカテゴリ名",
    order="変更後の表示順。小さい値ほど先に表示されます",
)
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def category_edit(
    interaction: discord.Interaction,
    category: int,
    name: app_commands.Range[str, 1, 100] | None = None,
    order: app_commands.Range[int, 0] | None = None,
) -> None:
    bot = get_bot(interaction)
    if name is None and order is None:
        await interaction.response.send_message(
            embed=_response_embed("変更内容がありません", "変更内容を1つ以上指定してください。"),
            ephemeral=True,
        )
        return

    updated = await bot.db.role_panel.update_category(
        category,
        name=name,
        display_order=order,
    )
    if updated is None:
        await interaction.response.send_message(
            embed=_response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return

    await _refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを編集しました: command=/rolepanel category edit "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category} name={name} order={order}"
    )
    await interaction.response.send_message(
        embed=_response_embed("カテゴリを更新しました", f"カテゴリ `{updated.name}` を更新しました。")
    )


@category_group.command(name="remove", description="ロールパネルカテゴリを削除します")
@app_commands.rename(category="カテゴリ")
@app_commands.describe(category="削除するカテゴリ")
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def category_remove(interaction: discord.Interaction, category: int) -> None:
    bot = get_bot(interaction)
    deleted = await bot.db.role_panel.delete_category(category)
    if not deleted:
        await interaction.response.send_message(
            embed=_response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return

    await _refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリを削除しました: command=/rolepanel category remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category}"
    )
    await interaction.response.send_message(
        embed=_response_embed("カテゴリを削除しました", "カテゴリを削除しました。")
    )


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
            embed=_response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return

    role_ids = [role.role_id for role in category_data.roles]
    logger.info(
        "ロールパネルカテゴリのロール編集を開始しました: command=/rolepanel edit_role "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category}"
    )
    await interaction.response.send_message(
        embed=_response_embed("ロールを編集", f"`{category_data.name}` に表示するロールを選択してください。"),
        view=RolePanelAdminRoleEditView(
            RolePanelAdminRoleSelect(
                category,
                role_ids,
                interaction.user.id,
                lambda: _refresh_panel_if_loaded(bot),
            )
        ),
        ephemeral=True,
    )


@rolepanel_group.command(name="require_boost", description="カテゴリのロールをブースター限定設定を変更します。")
@app_commands.rename(category="カテゴリ", required="ブースター限定")
@app_commands.describe(
    category="設定を変更するカテゴリ",
    required="ブースター限定にするかどうか",
)
@app_commands.autocomplete(category=category_autocomplete)
@admin_only
async def required_edit(interaction: discord.Interaction, category: int, required: bool) -> None:
    bot = get_bot(interaction)
    updated = await bot.db.role_panel.update_category(category, requires_boost=required)
    if updated is None:
        await interaction.response.send_message(
            embed=_response_embed("カテゴリが見つかりません", "指定されたカテゴリが見つかりません。"),
            ephemeral=True,
        )
        return

    await _refresh_panel_if_loaded(bot)
    logger.info(
        "ロールパネルカテゴリのブースト必須条件を更新しました: command=/rolepanel edit_required_role "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"category_id={category} required={required}"
    )
    await interaction.response.send_message(
        embed=_response_embed(
            "ブースター限定設定を更新しました",
            f"`{updated.name}` のブースター限定設定を {'有効' if required else '無効'} にしました。",
        ),
        ephemeral=True,
    )


@rolepanel_group.command(name="refresh", description="ロールパネルを再描画します")
@admin_only
async def refresh(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    refreshed = False
    cog = _get_rolepanel_cog(bot)
    if cog is not None:
        refreshed = await cog.send_or_update_role_panel()
    logger.info(
        "ロールパネルの再描画を実行しました: command=/rolepanel refresh "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"refreshed={refreshed}"
    )
    await interaction.response.send_message(
        embed=_response_embed(
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


def register_rolepanel_feature(bot: AsteroidBot) -> None:
    register_group(bot, rolepanel_group)


async def setup(bot: AsteroidBot) -> None:
    get_rolepanel_service(bot)
    register_rolepanel_feature(bot)
    await bot.add_cog(RolePanelCog(bot))

from __future__ import annotations

import datetime
from logging import getLogger

import discord
from discord import app_commands
from pytimeparse import parse

from app.common.command_groups import get_bot, register_group
from app.common.guild_scope import GuildScopedView
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.core.bot import AsteroidBot

from .service import (
    generate_reason,
    give_crime_record_role,
    log_punishment_action,
    require_punishment_context,
    send_punish_message,
)
from .views import PermRoleSelect

logger = getLogger(__name__)

punish_group = app_commands.Group(
    name="punish",
    description="処罰コマンド",
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)


@punish_group.command(name="none", description="処罰: 無し")
@app_commands.rename(defendant="対象ユーザー", content="レポート内容", reason="理由")
@app_commands.guild_only()
@admin_only
async def punish_none(interaction: discord.Interaction, defendant: discord.User, content: str, reason: str) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    _, _, punishment_board = context
    log_punishment_action("無し", interaction, defendant.id)
    await punishment_board.send(
        f"```{defendant.name}\n"
        f"日付: {datetime.datetime.now().strftime('%m/%d')}\n"
        f"レポート内容: {content}\n"
        "処罰: 無し\n"
        f"理由: {reason}```"
    )
    await interaction.response.send_message("送信完了です！")


@punish_group.command(name="lecture", description="処罰: 口頭注意")
@app_commands.rename(violator="対象ユーザー", reason="理由")
@app_commands.guild_only()
@admin_only
async def lecture(interaction: discord.Interaction, violator: discord.User, reason: str) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    _, _, punishment_board = context
    log_punishment_action("口頭注意", interaction, violator.id)
    await send_punish_message(punishment_board, violator, reason, "口頭注意", None)
    await interaction.response.send_message("送信完了です！")


@punish_group.command(name="delete", description="処罰: メッセージ削除")
@app_commands.rename(violator="対象ユーザー", reason="理由")
@app_commands.guild_only()
@admin_only
async def delete(interaction: discord.Interaction, violator: discord.User, reason: str) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    _, _, punishment_board = context
    log_punishment_action("メッセージ削除", interaction, violator.id)
    await send_punish_message(punishment_board, violator, reason, "メッセージ削除", None)
    await interaction.response.send_message("送信完了です！")


@punish_group.command(name="timeout", description="処罰: タイムアウト")
@app_commands.rename(violator="対象ユーザー", duration="期間", reason="理由", probation="執行猶予")
@app_commands.guild_only()
@admin_only
async def timeout(
    interaction: discord.Interaction,
    violator: discord.User,
    duration: str,
    reason: str,
    probation: str | None = None,
) -> None:
    length = parse(duration)
    if length is None:
        logger.debug(f"タイムアウト時間の解析に失敗しました: value={duration} moderator_id={interaction.user.id}")
        await interaction.response.send_message(
            f"`{duration}`は無効なフォーマットです！\n対応する単位は: w, d, h, m, s", ephemeral=True
        )
        return
    if length > 2419200:
        logger.debug(
            f"タイムアウト時間が長すぎます: duration={duration} seconds={length} moderator_id={interaction.user.id}"
        )
        await interaction.response.send_message(
            "指定された時間は長すぎます！\nタイムアウトできる最長の期間は28日間（4週間）です。", ephemeral=True
        )
        return

    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    guild, moderator, punishment_board = context
    log_punishment_action("タイムアウト", interaction, violator.id, probation=probation, duration=duration)
    failed = await give_crime_record_role(bot, guild, violator, moderator)
    if not failed and probation is None:
        member = guild.get_member(violator.id)
        if member is not None:
            await member.timeout(datetime.timedelta(seconds=length), reason=generate_reason(moderator))

    await send_punish_message(punishment_board, violator, reason, "タイムアウト", probation, duration)
    warning = (
        "\n:warning:メンバーが見つからなかったためタイムアウト・前科ロールの付与をできませんでした！" if failed else ""
    )
    await interaction.response.send_message("送信完了です！" + warning)


@punish_group.command(name="disrobe", description="処罰: 権限剥奪")
@app_commands.rename(violator="対象ユーザー", reason="理由", probation="執行猶予")
@app_commands.guild_only()
@admin_only
async def disrobe(
    interaction: discord.Interaction, violator: discord.Member, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    if interaction.guild is None:
        await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)
        return
    logger.debug(
        "権限剥奪対象の選択を開始します: "
        f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"moderator_id={interaction.user.id if interaction.user is not None else None} "
        f"target_id={violator.id} probation={probation}"
    )
    logger.info(
        "権限剥奪の対象ロール選択を開始しました: command=/punish disrobe "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={violator.id} probation={probation}"
    )
    perms_role_id_list = bot.config.permission_roles_id_list.enabled_role_ids()
    options = []
    for role_id in perms_role_id_list:
        role = interaction.guild.get_role(role_id)
        if role is not None and role in violator.roles:
            options.append(discord.SelectOption(label=role.name, value=str(role.id)))

    view = GuildScopedView(timeout=300)
    if options:
        view.add_item(PermRoleSelect(bot, violator, options, reason, probation, interaction.user.id))
        await interaction.response.send_message(content=f"{violator.mention} からどの権限を剥奪しますか？", view=view)
    else:
        await interaction.response.send_message("剥奪対象の権限ロールが見つかりませんでした。", ephemeral=True)


@punish_group.command(name="mute", description="処罰: MUTE")
@app_commands.rename(user="対象ユーザー", reason="理由", probation="執行猶予")
@app_commands.guild_only()
@admin_only
async def mute(
    interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    guild, moderator, punishment_board = context
    log_punishment_action("MUTE", interaction, user.id, probation=probation)
    failed = await give_crime_record_role(bot, guild, user, moderator)
    if not failed and probation is None:
        mute_role = guild.get_role(bot.config.punish.mute_role_id)
        member = guild.get_member(user.id)
        if mute_role is not None and member is not None:
            await member.add_roles(mute_role, reason=generate_reason(moderator))
    await send_punish_message(punishment_board, user, reason, "MUTE", probation)
    warning = (
        "\n:warning:メンバーが見つからなかったため前科ロール・MUTEロールの付与をできませんでした！" if failed else ""
    )
    await interaction.response.send_message("送信完了です！" + warning)


@punish_group.command(name="forbid", description="処罰: 閲覧禁止")
@app_commands.rename(user="対象ユーザー", reason="理由", probation="執行猶予")
@app_commands.guild_only()
@admin_only
async def forbid(
    interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    guild, moderator, punishment_board = context
    log_punishment_action("閲覧禁止", interaction, user.id, probation=probation)
    failed = await give_crime_record_role(bot, guild, user, moderator)
    if not failed and probation is None:
        forbid_role = guild.get_role(bot.config.punish.forbid_role_id)
        member = guild.get_member(user.id)
        if forbid_role is not None and member is not None:
            await member.add_roles(forbid_role, reason=generate_reason(moderator))
    await send_punish_message(punishment_board, user, reason, "閲覧禁止", probation)
    warning = (
        "\n:warning:メンバーが見つからなかったため前科ロール・閲覧禁止ロールの付与をできませんでした！"
        if failed
        else ""
    )
    await interaction.response.send_message("送信完了です！" + warning)


@punish_group.command(name="ban", description="処罰: BAN")
@app_commands.rename(user="対象ユーザー", reason="理由", probation="執行猶予")
@app_commands.guild_only()
@admin_only
async def ban(interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    guild, moderator, punishment_board = context
    log_punishment_action("BAN", interaction, user.id, probation=probation)
    await send_punish_message(punishment_board, user, reason, "BAN", probation)

    failed = False
    if probation is None:
        await guild.ban(user, reason=generate_reason(moderator))
    else:
        failed = await give_crime_record_role(bot, guild, user, moderator)

    warning = "\n:warning:メンバーが見つからなかったため前科ロールを付与できませんでした！" if failed else ""
    await interaction.response.send_message("送信完了です！" + warning)


async def setup(bot: AsteroidBot) -> None:
    register_group(bot, punish_group)

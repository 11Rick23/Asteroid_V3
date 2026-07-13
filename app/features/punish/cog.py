from __future__ import annotations

import datetime
import re
from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.guild_scope import GuildScopedView
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.core.bot import AsteroidBot

from . import messages
from .service import (
    generate_reason,
    give_crime_record_role,
    log_punishment_action,
    require_punishment_context,
    send_punish_message,
)
from .views import PermRoleSelect

logger = getLogger(__name__)
_DURATION_PATTERN = re.compile(r"\s*(\d+(?:\.\d+)?|\.\d+)\s*([wdhms])\s*,?", re.IGNORECASE)
_SECONDS_BY_UNIT = {
    "w": 604800,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}


def parse_timeout_duration(duration: str) -> float | None:
    seconds = 0.0
    position = 0
    matched = False
    for match in _DURATION_PATTERN.finditer(duration):
        if match.start() != position:
            return None
        matched = True
        seconds += float(match.group(1)) * _SECONDS_BY_UNIT[match.group(2).lower()]
        position = match.end()

    if not matched or duration[position:].strip():
        return None
    return seconds


punish_group = app_commands.Group(
    name="punish",
    description=messages.GROUP_DESCRIPTION,
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)


@punish_group.command(name="none", description=messages.NONE_DESCRIPTION)
@app_commands.rename(
    defendant=messages.TARGET_USER_LABEL, content=messages.REPORT_CONTENT_LABEL, reason=messages.REASON_LABEL
)
@app_commands.guild_only()
@admin_only
async def punish_none(interaction: discord.Interaction, defendant: discord.User, content: str, reason: str) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    _, _, punishment_board = context
    log_punishment_action(messages.PUNISHMENT_NONE, interaction, defendant.id)
    await punishment_board.send(
        messages.no_punishment_record(
            user_name=defendant.name,
            date_text=datetime.datetime.now().strftime("%m/%d"),
            content=content,
            reason=reason,
        )
    )
    await interaction.response.send_message(messages.SENT)


@punish_group.command(name="lecture", description=messages.LECTURE_DESCRIPTION)
@app_commands.rename(violator=messages.TARGET_USER_LABEL, reason=messages.REASON_LABEL)
@app_commands.guild_only()
@admin_only
async def lecture(interaction: discord.Interaction, violator: discord.User, reason: str) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    _, _, punishment_board = context
    log_punishment_action(messages.PUNISHMENT_LECTURE, interaction, violator.id)
    await send_punish_message(punishment_board, violator, reason, messages.PUNISHMENT_LECTURE, None)
    await interaction.response.send_message(messages.SENT)


@punish_group.command(name="delete", description=messages.DELETE_DESCRIPTION)
@app_commands.rename(violator=messages.TARGET_USER_LABEL, reason=messages.REASON_LABEL)
@app_commands.guild_only()
@admin_only
async def delete(interaction: discord.Interaction, violator: discord.User, reason: str) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    _, _, punishment_board = context
    log_punishment_action(messages.PUNISHMENT_DELETE, interaction, violator.id)
    await send_punish_message(punishment_board, violator, reason, messages.PUNISHMENT_DELETE, None)
    await interaction.response.send_message(messages.SENT)


@punish_group.command(name="timeout", description=messages.TIMEOUT_DESCRIPTION)
@app_commands.rename(
    violator=messages.TARGET_USER_LABEL,
    duration=messages.DURATION_LABEL,
    reason=messages.REASON_LABEL,
    probation=messages.PROBATION_LABEL,
)
@app_commands.guild_only()
@admin_only
async def timeout(
    interaction: discord.Interaction,
    violator: discord.User,
    duration: str,
    reason: str,
    probation: str | None = None,
) -> None:
    length = parse_timeout_duration(duration)
    if length is None:
        logger.debug(f"タイムアウト時間の解析に失敗しました: value={duration} moderator_id={interaction.user.id}")
        await interaction.response.send_message(messages.invalid_timeout_duration(duration=duration), ephemeral=True)
        return
    if length > 2419200:
        logger.debug(
            f"タイムアウト時間が長すぎます: duration={duration} seconds={length} moderator_id={interaction.user.id}"
        )
        await interaction.response.send_message(messages.TIMEOUT_TOO_LONG, ephemeral=True)
        return

    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    guild, moderator, punishment_board = context
    log_punishment_action(
        messages.PUNISHMENT_TIMEOUT, interaction, violator.id, probation=probation, duration=duration
    )
    failed = await give_crime_record_role(bot, guild, violator, moderator)
    if not failed and probation is None:
        member = guild.get_member(violator.id)
        if member is not None:
            await member.timeout(datetime.timedelta(seconds=length), reason=generate_reason(moderator))

    await send_punish_message(punishment_board, violator, reason, messages.PUNISHMENT_TIMEOUT, probation, duration)
    warning = messages.TIMEOUT_MEMBER_NOT_FOUND_WARNING if failed else ""
    await interaction.response.send_message(messages.SENT + warning)


@punish_group.command(name="disrobe", description=messages.DISROBE_DESCRIPTION)
@app_commands.rename(
    violator=messages.TARGET_USER_LABEL, reason=messages.REASON_LABEL, probation=messages.PROBATION_LABEL
)
@app_commands.guild_only()
@admin_only
async def disrobe(
    interaction: discord.Interaction, violator: discord.Member, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    if interaction.guild is None:
        await interaction.response.send_message(messages.GUILD_ONLY, ephemeral=True)
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
        await interaction.response.send_message(
            content=messages.disrobe_prompt(target_mention=violator.mention), view=view
        )
    else:
        await interaction.response.send_message(messages.NO_DISROBE_ROLES, ephemeral=True)


@punish_group.command(name="mute", description=messages.MUTE_DESCRIPTION)
@app_commands.rename(user=messages.TARGET_USER_LABEL, reason=messages.REASON_LABEL, probation=messages.PROBATION_LABEL)
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
    log_punishment_action(messages.PUNISHMENT_MUTE, interaction, user.id, probation=probation)
    failed = await give_crime_record_role(bot, guild, user, moderator)
    if not failed and probation is None:
        mute_role = guild.get_role(bot.config.punish.mute_role_id)
        member = guild.get_member(user.id)
        if mute_role is not None and member is not None:
            await member.add_roles(mute_role, reason=generate_reason(moderator))
    await send_punish_message(punishment_board, user, reason, messages.PUNISHMENT_MUTE, probation)
    warning = messages.MUTE_MEMBER_NOT_FOUND_WARNING if failed else ""
    await interaction.response.send_message(messages.SENT + warning)


@punish_group.command(name="forbid", description=messages.FORBID_DESCRIPTION)
@app_commands.rename(user=messages.TARGET_USER_LABEL, reason=messages.REASON_LABEL, probation=messages.PROBATION_LABEL)
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
    log_punishment_action(messages.PUNISHMENT_FORBID, interaction, user.id, probation=probation)
    failed = await give_crime_record_role(bot, guild, user, moderator)
    if not failed and probation is None:
        forbid_role = guild.get_role(bot.config.punish.forbid_role_id)
        member = guild.get_member(user.id)
        if forbid_role is not None and member is not None:
            await member.add_roles(forbid_role, reason=generate_reason(moderator))
    await send_punish_message(punishment_board, user, reason, messages.PUNISHMENT_FORBID, probation)
    warning = messages.FORBID_MEMBER_NOT_FOUND_WARNING if failed else ""
    await interaction.response.send_message(messages.SENT + warning)


@punish_group.command(name="ban", description=messages.BAN_DESCRIPTION)
@app_commands.rename(user=messages.TARGET_USER_LABEL, reason=messages.REASON_LABEL, probation=messages.PROBATION_LABEL)
@app_commands.guild_only()
@admin_only
async def ban(interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None) -> None:
    bot = get_bot(interaction)
    context = await require_punishment_context(bot, interaction)
    if context is None:
        return
    guild, moderator, punishment_board = context
    log_punishment_action(messages.PUNISHMENT_BAN, interaction, user.id, probation=probation)
    await send_punish_message(punishment_board, user, reason, messages.PUNISHMENT_BAN, probation)

    failed = False
    if probation is None:
        await guild.ban(user, reason=generate_reason(moderator))
    else:
        failed = await give_crime_record_role(bot, guild, user, moderator)

    warning = messages.CRIME_ROLE_MEMBER_NOT_FOUND_WARNING if failed else ""
    await interaction.response.send_message(messages.SENT + warning)


async def setup(bot: AsteroidBot) -> None:
    register_group(bot, punish_group)

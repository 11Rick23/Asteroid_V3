from __future__ import annotations

import datetime
from logging import getLogger

import discord
from discord import app_commands
from pytimeparse import parse

from app.common.command_groups import get_bot, register_group
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger(__name__)

punish_group = app_commands.Group(name="punish", description="処罰コマンド")


def generate_reason(moderator: discord.Member) -> str:
    return f"[{generate_timestamp()}] {moderator.name} によって処罰が行われました。"


def log_punishment_action(
    action: str,
    interaction: discord.Interaction,
    target_id: int,
    *,
    probation: str | None = None,
    duration: str | None = None,
) -> None:
    logger.info(
        f"処罰を実行します: action={action} "
        f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"moderator_id={interaction.user.id if interaction.user is not None else None} "
        f"target_id={target_id} probation={probation} duration={duration}"
    )


async def send_punish_message(
    punishment_board: discord.TextChannel,
    user: discord.User | discord.Member,
    reason: str,
    punishment: str,
    probation: str | None,
    duration: str | None = None,
) -> None:
    message = (
        f"```{user.name} {user.id}\n"
        f"日付: {datetime.datetime.now().strftime('%m/%d')}\n"
        f"違反内容: {reason}\n"
        f"処罰: {punishment}"
        + (f"\n期間: {duration}" if duration is not None else "")
        + (f"\n執行猶予: {probation}```" if probation is not None else "```")
    )
    await punishment_board.send(message)
    try:
        await user.send(message)
    except discord.Forbidden:
        logger.debug(f"処罰DMの送信に失敗しました: target_id={user.id}")


async def give_crime_record_role(
    bot: AsteroidBot, guild: discord.Guild, user: discord.User | discord.Member, moderator: discord.Member
) -> bool:
    member = guild.get_member(user.id)
    if member is None:
        logger.warning(f"前科ロールの付与対象メンバーが見つかりませんでした: guild_id={guild.id} target_id={user.id}")
        return True

    crimes = sum(1 for role in member.roles if role.name.startswith("前科"))
    crime_roles = bot.config.punish.crime_record_role_id_list
    if crimes < len(crime_roles):
        role = guild.get_role(crime_roles[crimes])
        if role is not None:
            await member.add_roles(role, reason=generate_reason(moderator))
            logger.info(f"前科ロールを付与しました: guild_id={guild.id} target_id={user.id} role_id={role.id}")
        else:
            logger.warning(
                f"前科ロールが見つかりませんでした: guild_id={guild.id} "
                f"target_id={user.id} role_id={crime_roles[crimes]}"
            )
    return False


class PermRoleSelect(discord.ui.Select):
    def __init__(
        self,
        bot: AsteroidBot,
        target: discord.Member,
        select_options: list[discord.SelectOption],
        reason: str,
        probation: str | None,
    ):
        super().__init__(
            placeholder="剥奪する権限ロールを選択…",
            options=select_options,
            min_values=1,
            max_values=max(1, len(select_options)),
        )
        self.bot = bot
        self.target = target
        self.reason = reason
        self.probation = probation

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            logger.warning(f"権限剥奪UIをサーバー外で受信しました: target_id={getattr(self.target, 'id', None)}")
            await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)
            return

        log_punishment_action("権限剥奪", interaction, self.target.id, probation=self.probation)
        await give_crime_record_role(self.bot, guild, self.target, interaction.user)
        roles = [guild.get_role(int(value)) for value in self.values]
        roles = [role for role in roles if role is not None]
        if self.probation is None and roles:
            await self.target.remove_roles(*roles, reason=generate_reason(interaction.user), atomic=False)

        punishment_board = guild.get_channel(self.bot.config.punish.punishment_board_channel_id)
        role_names = [role.name for role in roles]
        await send_punish_message(punishment_board, self.target, self.reason, f"権限剥奪 {role_names}", self.probation)
        await interaction.response.edit_message(content="送信完了です！", view=None)


@punish_group.command(name="none", description="処罰: 無し")
@app_commands.guild_only()
async def punish_none(interaction: discord.Interaction, defendant: discord.User, content: str, reason: str) -> None:
    bot = get_bot(interaction)
    log_punishment_action("無し", interaction, defendant.id)
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await punishment_board.send(
        f"```{defendant.name}\n"
        f"日付: {datetime.datetime.now().strftime('%m/%d')}\n"
        f"レポート内容: {content}\n"
        "処罰: 無し\n"
        f"理由: {reason}```"
    )
    await interaction.response.send_message("送信完了です！")


@punish_group.command(name="lecture", description="処罰: 口頭注意")
@app_commands.guild_only()
async def lecture(interaction: discord.Interaction, violator: discord.User, reason: str) -> None:
    bot = get_bot(interaction)
    log_punishment_action("口頭注意", interaction, violator.id)
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await send_punish_message(punishment_board, violator, reason, "口頭注意", None)
    await interaction.response.send_message("送信完了です！")


@punish_group.command(name="delete", description="処罰: メッセージ削除")
@app_commands.guild_only()
async def delete(interaction: discord.Interaction, violator: discord.User, reason: str) -> None:
    bot = get_bot(interaction)
    log_punishment_action("メッセージ削除", interaction, violator.id)
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await send_punish_message(punishment_board, violator, reason, "メッセージ削除", None)
    await interaction.response.send_message("送信完了です！")


@punish_group.command(name="timeout", description="処罰: タイムアウト")
@app_commands.guild_only()
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
    log_punishment_action("タイムアウト", interaction, violator.id, probation=probation, duration=duration)
    failed = await give_crime_record_role(bot, interaction.guild, violator, interaction.user)
    if not failed and probation is None:
        member = interaction.guild.get_member(violator.id)
        if member is not None:
            await member.timeout(datetime.timedelta(seconds=length), reason=generate_reason(interaction.user))

    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await send_punish_message(punishment_board, violator, reason, "タイムアウト", probation, duration)
    warning = (
        "\n:warning:メンバーが見つからなかったためタイムアウト・前科ロールの付与をできませんでした！" if failed else ""
    )
    await interaction.response.send_message("送信完了です！" + warning)


@punish_group.command(name="disrobe", description="処罰: 権限剥奪")
@app_commands.guild_only()
async def disrobe(
    interaction: discord.Interaction, violator: discord.Member, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    logger.info(
        "権限剥奪対象の選択を開始します: "
        f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"moderator_id={interaction.user.id if interaction.user is not None else None} "
        f"target_id={violator.id} probation={probation}"
    )
    perms_role_id_list = bot.config.permission_roles_id_list.enabled_role_ids()
    options = []
    for role_id in perms_role_id_list:
        role = interaction.guild.get_role(role_id)
        if role in violator.roles:
            options.append(discord.SelectOption(label=role.name, value=str(role.id)))

    view = discord.ui.View(timeout=300)
    if options:
        view.add_item(PermRoleSelect(bot, violator, options, reason, probation))
        await interaction.response.send_message(content=f"{violator.mention} からどの権限を剥奪しますか？", view=view)
    else:
        await interaction.response.send_message("剥奪対象の権限ロールが見つかりませんでした。", ephemeral=True)


@punish_group.command(name="mute", description="処罰: MUTE")
@app_commands.guild_only()
async def mute(
    interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    log_punishment_action("MUTE", interaction, user.id, probation=probation)
    failed = await give_crime_record_role(bot, interaction.guild, user, interaction.user)
    if not failed and probation is None:
        mute_role = interaction.guild.get_role(bot.config.punish.mute_role_id)
        member = interaction.guild.get_member(user.id)
        if mute_role is not None and member is not None:
            await member.add_roles(mute_role, reason=generate_reason(interaction.user))
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await send_punish_message(punishment_board, user, reason, "MUTE", probation)
    warning = (
        "\n:warning:メンバーが見つからなかったため前科ロール・MUTEロールの付与をできませんでした！" if failed else ""
    )
    await interaction.response.send_message("送信完了です！" + warning)


@punish_group.command(name="forbid", description="処罰: 閲覧禁止")
@app_commands.guild_only()
async def forbid(
    interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None
) -> None:
    bot = get_bot(interaction)
    log_punishment_action("閲覧禁止", interaction, user.id, probation=probation)
    failed = await give_crime_record_role(bot, interaction.guild, user, interaction.user)
    if not failed and probation is None:
        forbid_role = interaction.guild.get_role(bot.config.punish.forbid_role_id)
        member = interaction.guild.get_member(user.id)
        if forbid_role is not None and member is not None:
            await member.add_roles(forbid_role, reason=generate_reason(interaction.user))
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await send_punish_message(punishment_board, user, reason, "閲覧禁止", probation)
    warning = (
        "\n:warning:メンバーが見つからなかったため前科ロール・閲覧禁止ロールの付与をできませんでした！"
        if failed
        else ""
    )
    await interaction.response.send_message("送信完了です！" + warning)


@punish_group.command(name="ban", description="処罰: BAN")
@app_commands.guild_only()
async def ban(interaction: discord.Interaction, user: discord.User, reason: str, probation: str | None = None) -> None:
    bot = get_bot(interaction)
    log_punishment_action("BAN", interaction, user.id, probation=probation)
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    await send_punish_message(punishment_board, user, reason, "BAN", probation)

    failed = False
    if probation is None:
        await interaction.guild.ban(user, reason=generate_reason(interaction.user))
    else:
        failed = await give_crime_record_role(bot, interaction.guild, user, interaction.user)

    warning = "\n:warning:メンバーが見つからなかったため前科ロールを付与できませんでした！" if failed else ""
    await interaction.response.send_message("送信完了です！" + warning)


async def setup(bot: AsteroidBot) -> None:
    register_group(bot, punish_group)

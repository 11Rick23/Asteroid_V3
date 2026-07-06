from __future__ import annotations

from calendar import isleap
from datetime import date, datetime, time
from logging import getLogger
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app.common.command_groups import get_bot, register_group
from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable
from app.common.error_reporting import report_background_task_error
from app.common.permissions import admin_only
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger(__name__)

DEFAULT_YEAR = 2000
BIRTHDAY_EMOJI = "🎂"
TOKYO_TZ = ZoneInfo("Asia/Tokyo")
birthday_group = app_commands.Group(name="birthday", description="誕生日に関するコマンド")


def validate_date(month: int, day: int) -> bool:
    try:
        datetime(DEFAULT_YEAR, month, day)
        return True
    except ValueError:
        return False


def convert_date(today: date, birthday: date) -> str:
    if (birthday.month, birthday.day) < (today.month, today.day):
        try:
            birthday = birthday.replace(year=today.year + 1)
        except ValueError:
            birthday = date(today.year + 1, 2, 28)

    if birthday.year == DEFAULT_YEAR:
        birthday = birthday.replace(year=today.year)

    diff = (birthday - today).days
    return {0: "今日", 1: "明日", 2: "明後日"}.get(diff, birthday.strftime("%Y年%m月%d日"))


class Birthday(commands.Cog):
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot
        self.announce_birthday.start()

    async def cog_unload(self) -> None:
        self.announce_birthday.cancel()

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=TOKYO_TZ))
    async def announce_birthday(self) -> None:
        guild_id = self.bot.config.discord.guild_id
        birthday_channel_id = self.bot.config.birthday.birthday_channel_id
        birthday_role_id = self.bot.config.birthday.birthday_role_id
        if not guild_id or not birthday_channel_id or not birthday_role_id:
            logger.warning("誕生日アナウンス設定が不足しています。")
            return

        logger.debug("誕生日アナウンスを開始します。")
        today = datetime.now().date()
        data = await self.bot.db.user_birthdays.get_user_data_by_date(today.replace(year=DEFAULT_YEAR))
        if not isleap(today.year) and today.month == 2 and today.day == 28:
            data.extend(await self.bot.db.user_birthdays.get_user_data_by_date(date(DEFAULT_YEAR, 2, 29)))

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            logger.warning(f"誕生日アナウンス対象ギルドが見つかりませんでした: guild_id={guild_id}")
            return

        announce_channel = guild.get_channel(birthday_channel_id)
        birthday_role = guild.get_role(birthday_role_id)
        messageable_channel = as_messageable(announce_channel)
        if messageable_channel is None or birthday_role is None:
            logger.warning(
                f"誕生日アナウンス先を解決できませんでした: guild_id={guild.id} "
                f"channel_id={birthday_channel_id} role_id={birthday_role_id}"
            )
            return

        remove_birthday_role_user_id_list = [member.id for member in birthday_role.members]
        announced_count = 0
        for user_data in data:
            member = guild.get_member(user_data.user_id)
            if member is None:
                continue
            await member.add_roles(birthday_role, reason=f"[{generate_timestamp()}] 誕生日機能により付与されました。")
            await messageable_channel.send(f"# 今日は {member.mention} の誕生日だ！おめでとう！{BIRTHDAY_EMOJI}")
            announced_count += 1

        removed_count = 0
        for user_id in remove_birthday_role_user_id_list:
            member = guild.get_member(user_id)
            if member is not None and member.id not in {user_data.user_id for user_data in data}:
                await member.remove_roles(
                    birthday_role, reason=f"[{generate_timestamp()}] 誕生日機能により剥奪されました。"
                )
                removed_count += 1

        logger.debug(
            f"誕生日アナウンスが完了しました: guild_id={guild.id} "
            f"birthday_count={announced_count} removed_count={removed_count}"
        )

    @announce_birthday.error
    async def announce_birthday_error(self, error: BaseException) -> None:
        await report_background_task_error(self.bot, "birthday.announce_birthday", error)


@birthday_group.command(name="set", description="誕生日を設定")
@app_commands.rename(month="月", day="日")
@app_commands.describe(month="誕生日の月", day="誕生日の日")
async def birthday_set(interaction: discord.Interaction, month: int, day: int) -> None:
    bot = get_bot(interaction)
    if not validate_date(month, day):
        logger.debug(f"存在しない誕生日の設定を拒否しました: user_id={interaction.user.id} month={month} day={day}")
        await interaction.response.send_message(
            embed=discord.Embed(color=AsteroidColor.WARNING, description=f"`{month}/{day}` は存在しません。")
        )
        return
    await bot.db.user_birthdays.upsert_data(interaction.user.id, date(DEFAULT_YEAR, month, day))
    logger.debug(
        "誕生日を設定しました: command=/birthday set "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} month={month} day={day}"
    )
    await interaction.response.send_message(
        embed=discord.Embed(color=AsteroidColor.SUCCESS, description=f"誕生日を `{month}/{day}` に設定しました。")
    )


@birthday_group.command(name="set_others", description="他人の誕生日を設定")
@app_commands.rename(user="ユーザー", month="月", day="日")
@app_commands.describe(user="設定するユーザー", month="誕生日の月", day="誕生日の日")
@admin_only
async def birthday_set_others(interaction: discord.Interaction, user: discord.User, month: int, day: int) -> None:
    bot = get_bot(interaction)
    if not validate_date(month, day):
        logger.debug(
            "他人の誕生日設定を拒否しました: command=/birthday set_others reason=invalid_date "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"actor_id={interaction.user.id} target_id={user.id} month={month} day={day}"
        )
        await interaction.response.send_message(
            embed=discord.Embed(color=AsteroidColor.WARNING, description=f"`{month}/{day}` は存在しません。")
        )
        return
    await bot.db.user_birthdays.upsert_data(user.id, date(DEFAULT_YEAR, month, day))
    logger.info(
        "他人の誕生日を設定しました: command=/birthday set_others "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} target_id={user.id} month={month} day={day}"
    )
    await interaction.response.send_message(
        embed=discord.Embed(
            color=AsteroidColor.SUCCESS, description=f"{user.mention} の誕生日を `{month}/{day}` に設定しました。"
        )
    )


@birthday_group.command(name="show", description="誕生日を表示")
@app_commands.rename(user="ユーザー")
@app_commands.describe(user="誕生日を表示するユーザー")
async def birthday_show(interaction: discord.Interaction, user: discord.User | None = None) -> None:
    bot = get_bot(interaction)
    target_user: discord.abc.User = user or interaction.user
    user_data = await bot.db.user_birthdays.get_user_data(target_user.id)
    if user_data is None:
        logger.debug(
            "誕生日表示をスキップしました: command=/birthday show "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"user_id={interaction.user.id} target_id={target_user.id} result=not_found"
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                color=AsteroidColor.WARNING, description=f"{target_user.mention} はまだ誕生日を設定していません。"
            )
        )
        return
    logger.debug(
        "誕生日を表示しました: command=/birthday show "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} target_id={target_user.id}"
    )
    await interaction.response.send_message(
        embed=discord.Embed(
            color=AsteroidColor.SUCCESS,
            description=f"{target_user.mention} の誕生日は `{user_data.date.month}/{user_data.date.day}` です。",
        )
    )


@birthday_group.command(name="remove", description="誕生日を削除")
@app_commands.rename(user="ユーザー")
@app_commands.describe(user="誕生日を削除するユーザー")
async def birthday_remove(interaction: discord.Interaction, user: discord.User | None = None) -> None:
    bot = get_bot(interaction)
    actor = interaction.user
    if user and (not isinstance(actor, discord.Member) or not actor.guild_permissions.administrator):
        logger.debug(f"誕生日削除の権限が不足しています: actor_id={interaction.user.id} target_id={user.id}")
        await interaction.response.send_message(
            embed=discord.Embed(
                color=AsteroidColor.WARNING,
                description="管理者権限を持っていない場合、`user` オプションは使用できません。",
            )
        )
        return
    target_user: discord.abc.User = user or interaction.user
    data = await bot.db.user_birthdays.get_user_data(target_user.id)
    if not data:
        logger.debug(f"未設定の誕生日削除を拒否しました: target_id={target_user.id}")
        await interaction.response.send_message(
            embed=discord.Embed(
                color=AsteroidColor.WARNING, description=f"{target_user.mention} はまだ誕生日を設定していません。"
            )
        )
        return
    await bot.db.user_birthdays.delete_data(target_user.id)
    if target_user.id == interaction.user.id:
        logger.debug(
            "誕生日を削除しました: command=/birthday remove "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"user_id={interaction.user.id} target_id={target_user.id}"
        )
    else:
        logger.info(
            "他人の誕生日を削除しました: command=/birthday remove "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"actor_id={interaction.user.id} target_id={target_user.id}"
        )
    await interaction.response.send_message(
        embed=discord.Embed(color=AsteroidColor.SUCCESS, description=f"{target_user.mention} の誕生日を削除しました。")
    )


@birthday_group.command(name="list", description="次の誕生日10人をリスト形式で表示")
async def birthday_list(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    data = await bot.db.user_birthdays.get_sorted_all_user_data()
    if len(data) == 0:
        logger.debug(
            "誕生日リストを表示しました: command=/birthday list "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"user_id={interaction.user.id} result_count=0"
        )
        await interaction.response.send_message(
            embed=discord.Embed(color=AsteroidColor.WARNING, description="まだ誰も誕生日を設定していません。")
        )
        return

    today = datetime.now().date()
    future_data = [_data for _data in data if (_data.date.month, _data.date.day) >= (today.month, today.day)]
    if len(future_data) < 10:
        future_data += [_data for _data in data if (_data.date.month, _data.date.day) < (today.month, today.day)]

    logger.debug(
        "誕生日リストを表示しました: command=/birthday list "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} result_count={min(len(future_data), 10)}"
    )
    embed = discord.Embed(color=AsteroidColor.INFO, title=f"{BIRTHDAY_EMOJI} 誕生日リスト")
    for _index, entry in enumerate(future_data[:10]):
        user = bot.get_user(entry.user_id)
        if user is None:
            try:
                user = await bot.fetch_user(entry.user_id)
            except discord.NotFound:
                continue
        if user is None:
            continue
        embed.add_field(name=convert_date(today, entry.date), value=user.mention, inline=False)
    await interaction.response.send_message(embed=embed)


async def setup(bot: AsteroidBot) -> None:
    register_group(bot, birthday_group)
    await bot.add_cog(Birthday(bot))

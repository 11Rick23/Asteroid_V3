from __future__ import annotations

import datetime
import random
from time import time
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app.common.command_groups import get_bot, register_setup_command
from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    build_power_ranking_embed,
    build_shard_ranking_embed,
    send_grade_up_message,
    send_prestige_announce,
    send_prestige_up_message,
)
from app.features.leveling.commands.admin_command import register_leveling_admin_commands
from app.features.leveling.commands.command import register_leveling_commands
from app.features.leveling.commands.power_command import register_power_commands
from app.features.leveling.commands.shard_command import register_shard_commands
from app.features.leveling.manage_reward_role import sync_grade_prestige_role
from app.features.leveling.service import (
    apply_voice_xp_claim_side_effects,
    build_voice_xp_claim_message,
    claim_voice_xp_rewards,
)


class ClaimVoiceXP(discord.ui.View):
    def __init__(self, bot: AsteroidBot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="VC経験値を獲得する", style=discord.ButtonStyle.success, custom_id="claim_voice_xp")
    async def button_callback(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        claim_result = await claim_voice_xp_rewards(self.bot, interaction.user.id)
        if claim_result is None:
            await interaction.response.send_message("VC経験値を獲得していません", ephemeral=True)
            return

        await interaction.response.send_message(content=build_voice_xp_claim_message(interaction.user, claim_result))
        await apply_voice_xp_claim_side_effects(self.bot, interaction.channel, interaction.user, claim_result)


class LevelingSystemCore(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.cooldown: dict[int, float] = {}
        self.cooldown_time = self.bot.config.leveling.message_cooldown
        self.ranking_board_messages: list[discord.Message] = []
        self.voice_xp_claim.start()
        self.delete_expired_xp_boosts.start()
        self.update_ranking_board.start()
        self.monthly_ranking.start()

    def cog_unload(self) -> None:
        self.voice_xp_claim.cancel()
        self.delete_expired_xp_boosts.cancel()
        self.update_ranking_board.cancel()
        self.monthly_ranking.cancel()

    async def cog_load(self) -> None:
        self.bot.add_view(ClaimVoiceXP(self.bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        self.bot.remember_message(message)
        if message.author.bot or message.guild is None or message.guild.id not in self.bot.config.discord.guild_ids:
            return
        if message.author.id in self.cooldown and (self.cooldown[message.author.id] + self.cooldown_time) >= time():
            return

        self.cooldown[message.author.id] = time()
        increase = random.randint(
            self.bot.config.leveling.min_xp_per_message,
            self.bot.config.leveling.max_xp_per_message,
        )
        if message.channel.type == discord.ChannelType.voice:
            increase = int(increase * self.bot.config.leveling.voice_xp_adjust)

        async with self.bot.db.session() as session:
            monthly_power = await self.bot.db.monthly_powers.get_monthly_power_lock(
                session, message.author.id
            ) or await self.bot.db.monthly_powers.create_monthly_power_lock(session, message.author.id)
            await self.bot.db.monthly_powers.add_text_power_lock(session, monthly_power, increase)

            boost_increase = 0
            xp_boosts = await self.bot.db.xp_boosts.get_xp_boosts()
            if xp_boosts:
                total_boost_amount = 0
                for xp_boost in xp_boosts:
                    role = message.guild.get_role(xp_boost.role_id)
                    if role in message.author.roles:
                        total_boost_amount += xp_boost.boost_amount / 100
                if total_boost_amount < 1:
                    total_boost_amount += 1
                boost_increase = int(increase * total_boost_amount) - increase

            star_grade = await self.bot.db.star_grades.get_star_grade_lock(
                session, message.author.id
            ) or await self.bot.db.star_grades.create_star_grade_lock(session, message.author.id)
            star_grade, grade_up_amount_text, prestige_amount_text = await self.bot.db.star_grades.add_text_shard_lock(
                session, star_grade, increase
            )

            grade_up_amount_bonus = 0
            prestige_amount_bonus = 0
            if boost_increase > 0:
                (
                    star_grade,
                    grade_up_amount_bonus,
                    prestige_amount_bonus,
                ) = await self.bot.db.star_grades.add_bonus_shard_lock(session, star_grade, boost_increase)

            await session.commit()

        grade_up_amount = grade_up_amount_text + grade_up_amount_bonus
        prestige_amount = prestige_amount_text + prestige_amount_bonus
        if prestige_amount > 0:
            await send_prestige_up_message(message.channel, message.author, star_grade.prestige, prestige_amount)
            await send_prestige_announce(self.bot, message.author, star_grade.prestige)
        elif grade_up_amount > 0:
            await send_grade_up_message(message.channel, message.author, star_grade.grade, grade_up_amount)
        await sync_grade_prestige_role(self.bot, message.author, star_grade)

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=ZoneInfo("Asia/Tokyo")))
    async def monthly_ranking(self) -> None:
        if not self.bot.db.is_initialized():
            return
        now = datetime.datetime.now()
        if now.day != 1 or now.hour != 0 or now.minute != 0:
            return

        guild = self.bot.get_guild(self.bot.config.discord.guild_ids[0])
        if guild is None:
            return
        top1_role = guild.get_role(self.bot.config.leveling.top1_role_id)
        top10_role = guild.get_role(self.bot.config.leveling.top10_role_id)
        monthly_powers = await self.bot.db.monthly_powers.get_monthly_power_ranking(limit=10)
        remove_top10_role_users_id = [member.id for member in top10_role.members] if top10_role else []

        for monthly_power in monthly_powers:
            member = guild.get_member(monthly_power.user_id)
            if member is None:
                continue
            if monthly_power.ranking == 1 and top1_role is not None:
                await member.add_roles(
                    top1_role, reason=f"[{generate_timestamp()}] 月間ランキングにより付与されました"
                )
            if monthly_power.user_id in remove_top10_role_users_id:
                remove_top10_role_users_id.remove(monthly_power.user_id)
                continue
            if top10_role is not None:
                await member.add_roles(
                    top10_role, reason=f"[{generate_timestamp()}] 月間ランキングにより付与されました"
                )

        for user_id in remove_top10_role_users_id:
            member = guild.get_member(user_id)
            if member is not None and top10_role is not None:
                await member.remove_roles(
                    top10_role, reason=f"[{generate_timestamp()}] 月間ランキングにより剥奪されました"
                )

        monthly_power_ranking_text = "\n".join(
            f"> {monthly_power.ranking}位: <@{monthly_power.user_id}>" for monthly_power in monthly_powers
        )
        base_embed = discord.Embed(
            title="月間ランキング", description="月間ランキング 今回のTOP10", color=AsteroidColor.INFO
        )
        embed = build_power_ranking_embed(self.bot, monthly_powers, base_embed)[0]
        channel = self.bot.get_channel(self.bot.config.leveling.month_ranking_board_channel_id)
        if channel is not None:
            await channel.send(
                content=f"ということで、今回のtop10は...\n\n{monthly_power_ranking_text}\n\nこのようになりました！おめでとうございます！",
                embed=embed,
            )
        await self.bot.db.monthly_powers.truncate_table()
        await self.bot.db.voice_xp_limits.reset_voice_power()

    @tasks.loop(minutes=1)
    async def voice_xp_claim(self) -> None:
        if not self.bot.db.is_initialized():
            return
        for guild in self.bot.guilds:
            xp_boosts = await self.bot.db.xp_boosts.get_xp_boosts()
            for channel in guild.voice_channels:
                voice_active_members = [
                    member
                    for member in channel.members
                    if not member.bot
                    and member.voice
                    and not member.voice.mute
                    and not member.voice.deaf
                    and not member.voice.afk
                    and not member.voice.self_mute
                    and not member.voice.self_deaf
                ]
                if len(voice_active_members) < 2:
                    continue
                for member in voice_active_members:
                    async with self.bot.db.session() as session:
                        data = await self.bot.db.voice_xp_limits.get_voice_xp_limit_lock(
                            session, member.id
                        ) or await self.bot.db.voice_xp_limits.create_voice_xp_limit_lock(session, member.id)
                        full_notified = data.full_notify
                        half_notified = data.half_notify
                        increase = random.randint(
                            self.bot.config.leveling.min_xp_per_voice_minute,
                            self.bot.config.leveling.max_xp_per_voice_minute,
                        )

                        if data.voice_power < self.bot.config.leveling.voice_xp_limit:
                            fix_increase = int(increase * self.bot.config.leveling.voice_xp_adjust)
                            (
                                data,
                                half_limit_reached,
                                limit_reached,
                            ) = await self.bot.db.voice_xp_limits.add_voice_power_lock(
                                session, data, fix_increase, self.bot.config.leveling.voice_xp_limit
                            )
                            if limit_reached and not full_notified:
                                await self.voice_limit_reached_send(channel, member)
                                full_notified = True
                                half_notified = True
                            elif half_limit_reached and not half_notified:
                                await self.voice_half_limit_reached_send(channel, member)
                                half_notified = True

                        if (data.voice_shard + data.bonus_shard) < self.bot.config.leveling.voice_xp_limit:
                            fix_boost_increase = 0
                            if xp_boosts:
                                total_boost_amount = 0
                                for xp_boost in xp_boosts:
                                    role = guild.get_role(xp_boost.role_id)
                                    if role in member.roles:
                                        total_boost_amount += xp_boost.boost_amount / 100
                                if total_boost_amount < 1:
                                    total_boost_amount += 1
                                boost_increase = int(increase * total_boost_amount) - increase
                                fix_boost_increase = int(boost_increase * self.bot.config.leveling.voice_xp_adjust)

                            fix_increase = int(increase * self.bot.config.leveling.voice_xp_adjust)
                            (
                                data,
                                half_limit_reached,
                                limit_reached,
                            ) = await self.bot.db.voice_xp_limits.add_voice_shard_lock(
                                session, data, fix_increase, self.bot.config.leveling.voice_xp_limit
                            )
                            if fix_boost_increase > 0 and not limit_reached:
                                (
                                    data,
                                    half_limit_reached,
                                    limit_reached,
                                ) = await self.bot.db.voice_xp_limits.add_bonus_shard_lock(
                                    session, data, fix_boost_increase, self.bot.config.leveling.voice_xp_limit
                                )
                            if limit_reached and not full_notified:
                                await self.voice_limit_reached_send(channel, member)
                            elif half_limit_reached and not half_notified:
                                await self.voice_half_limit_reached_send(channel, member)
                        await session.commit()

    async def voice_limit_reached_send(self, channel: discord.VoiceChannel, member: discord.Member) -> None:
        await channel.send(
            embeds=[
                discord.Embed(
                    title="VC経験値獲得上限到達！",
                    description=(
                        f"**{member.mention}さんはVC経験値獲得上限に到達しました！\n"
                        "VC経験値を更に獲得するには`経験値を獲得する`ボタンを押すか、"
                        "`/claim_voice_xp` コマンドを実行してください！**"
                    ),
                    color=AsteroidColor.INFO,
                )
            ],
            view=ClaimVoiceXP(self.bot),
        )

    async def voice_half_limit_reached_send(self, channel: discord.VoiceChannel, member: discord.Member) -> None:
        return

    @tasks.loop(minutes=1)
    async def delete_expired_xp_boosts(self) -> None:
        if self.bot.db.is_initialized():
            await self.bot.db.xp_boosts.delete_expired_xp_boosts()

    @tasks.loop(minutes=1)
    async def update_ranking_board(self) -> None:
        if not self.bot.db.is_initialized() or len(self.ranking_board_messages) == 0:
            return
        monthly_powers = await self.bot.db.monthly_powers.get_monthly_power_ranking(limit=10)
        star_grades = await self.bot.db.star_grades.get_star_grade_ranking(limit=10)
        base_monthly = discord.Embed(
            title="月間ランキング",
            description="月間ランキング 現在のTOP10\n\n"
            f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
            f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
            f"{AsteroidEmoji.TRANSPARENT}",
            color=AsteroidColor.INFO,
        )
        base_shard = discord.Embed(
            title="恒常ランキング",
            description="恒常ランキング 現在のTOP10\n\n"
            f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
            f"{AsteroidEmoji.GRADE}: グレード\n"
            f"{AsteroidEmoji.SHARD}: シャード\n"
            f"{AsteroidEmoji.TRANSPARENT}",
            color=AsteroidColor.INFO,
        )
        monthly_embed = build_power_ranking_embed(self.bot, monthly_powers, base_monthly)
        shard_embed = build_shard_ranking_embed(self.bot, star_grades, base_shard)
        if not monthly_embed or not shard_embed:
            return
        for ranking_board_message in list(self.ranking_board_messages):
            try:
                await ranking_board_message.edit(embeds=[shard_embed[0], monthly_embed[0]])
            except discord.NotFound:
                self.ranking_board_messages.remove(ranking_board_message)

    @update_ranking_board.before_loop
    async def setup_ranking_board(self) -> None:
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.bot.config.leveling.ranking_board_channel_id)
        if channel is not None:
            message = await channel.send(
                embed=discord.Embed(title="ランキングボード", description="更新待機中", color=AsteroidColor.INFO)
            )
            self.ranking_board_messages.append(message)

    @update_ranking_board.after_loop
    async def cleanup_ranking_board(self) -> None:
        for message in self.ranking_board_messages:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        self.ranking_board_messages = []

    @delete_expired_xp_boosts.before_loop
    @monthly_ranking.before_loop
    async def before_task(self) -> None:
        await self.bot.wait_until_ready()

    @voice_xp_claim.after_loop
    async def before_voice_xp_claim(self) -> None:
        if self.voice_xp_claim.failed():
            await self.bot.wait_until_ready()
            self.voice_xp_claim.restart()


@app_commands.command(name="claim_voice_xp_button", description="VC経験値獲得用のボタンを設置します")
async def claim_voice_xp_button(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    embed = discord.Embed(
        title="VC経験値獲得はこちら", description="ボタンを押すとVC経験値を獲得します", color=AsteroidColor.INFO
    )
    await interaction.channel.send(embed=embed, view=ClaimVoiceXP(bot=bot))
    await interaction.response.send_message("VC経験値獲得用のボタンを設置しました！", ephemeral=True)


def register_leveling_feature(bot: AsteroidBot) -> None:
    register_leveling_commands(bot)
    register_shard_commands(bot)
    register_power_commands(bot)
    register_leveling_admin_commands(bot)
    register_setup_command(bot, claim_voice_xp_button)


async def setup(bot: AsteroidBot) -> None:
    register_leveling_feature(bot)
    await bot.add_cog(LevelingSystemCore(bot))

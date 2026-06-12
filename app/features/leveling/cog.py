from __future__ import annotations

import datetime
import random
from logging import getLogger
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from app.common.command_groups import register_setup_command
from app.core.bot import AsteroidBot
from app.features.leveling.commands.admin_command import register_leveling_admin_commands
from app.features.leveling.commands.command import register_leveling_commands
from app.features.leveling.commands.power_command import register_power_commands
from app.features.leveling.commands.shard_command import register_shard_commands
from app.features.leveling.message_handler import LevelingMessageHandler
from app.features.leveling.monthly import run_monthly_ranking
from app.features.leveling.ranking_board import RankingBoardPanel
from app.features.leveling.setup_command import claim_voice_xp_button
from app.features.leveling.views import ClaimVoiceXP

logger = getLogger(__name__)
TOKYO_TZ = ZoneInfo("Asia/Tokyo")


class LevelingSystemCore(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.message_handler = LevelingMessageHandler(bot)
        self.ranking_board = RankingBoardPanel(bot)
        self.voice_xp_claim.start()
        self.delete_expired_xp_boosts.start()
        self.update_ranking_board.start()
        self.monthly_ranking.start()

    async def cog_unload(self) -> None:
        self.voice_xp_claim.cancel()
        self.delete_expired_xp_boosts.cancel()
        self.update_ranking_board.cancel()
        self.monthly_ranking.cancel()
        self.ranking_board.unregister()

    async def cog_load(self) -> None:
        self.bot.add_view(ClaimVoiceXP(self.bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self.bot.is_operating_guild(message.guild):
            return
        await self.message_handler.handle(message)

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=TOKYO_TZ))
    async def monthly_ranking(self) -> None:
        await run_monthly_ranking(self.bot)

    @tasks.loop(minutes=1)
    async def voice_xp_claim(self) -> None:
        if not self.bot.db.is_initialized():
            return
        scanned_channel_count = 0
        rewarded_member_count = 0
        for guild in self.bot.guilds:
            if not self.bot.is_operating_guild(guild):
                continue
            xp_boosts = await self.bot.db.xp_boosts.get_xp_boosts()
            for channel in guild.voice_channels:
                scanned_channel_count += 1
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
                rewarded_member_count += len(voice_active_members)
                for member in voice_active_members:
                    increase = random.randint(
                        self.bot.config.leveling.min_xp_per_voice_minute,
                        self.bot.config.leveling.max_xp_per_voice_minute,
                    )
                    fix_increase = int(increase * self.bot.config.leveling.voice_xp_adjust)
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

                    accrual = await self.bot.db.leveling.accrue_voice_xp(
                        member.id,
                        voice_power_amount=fix_increase,
                        voice_shard_amount=fix_increase,
                        bonus_shard_amount=fix_boost_increase,
                        limit=self.bot.config.leveling.voice_xp_limit,
                    )
                    if accrual.notify_full_limit:
                        await self.voice_limit_reached_send(channel, member)
                    elif accrual.notify_half_limit:
                        await self.voice_half_limit_reached_send(channel, member)
        logger.debug(
            "VC経験値ループを実行しました: guild_count=1 "
            f"scanned_channel_count={scanned_channel_count} rewarded_member_count={rewarded_member_count}"
        )

    async def voice_limit_reached_send(self, channel: discord.VoiceChannel, member: discord.Member) -> None:
        await channel.send(
            view=ClaimVoiceXP(
                self.bot,
                title="VC経験値獲得上限到達！",
                description=(
                    f"**{member.mention}さんはVC経験値獲得上限に到達しました！\n"
                    "VC経験値を更に獲得するには`経験値を獲得する`ボタンを押すか、"
                    "`/claim_voice_xp` コマンドを実行してください！**"
                ),
            ),
        )
        logger.debug(
            f"VC経験値上限通知を送信しました: guild_id={channel.guild.id} channel_id={channel.id} user_id={member.id}"
        )

    async def voice_half_limit_reached_send(self, channel: discord.VoiceChannel, member: discord.Member) -> None:
        return

    @tasks.loop(minutes=1)
    async def delete_expired_xp_boosts(self) -> None:
        if self.bot.db.is_initialized():
            await self.bot.db.xp_boosts.delete_expired_xp_boosts()

    @tasks.loop(minutes=1)
    async def update_ranking_board(self) -> None:
        if not self.bot.db.is_initialized():
            return
        await self.ranking_board.refresh()

    @update_ranking_board.before_loop
    async def setup_ranking_board(self) -> None:
        await self.bot.wait_until_ready()
        await self.ranking_board.initialize()

    @delete_expired_xp_boosts.before_loop
    @monthly_ranking.before_loop
    async def before_task(self) -> None:
        await self.bot.wait_until_ready()

    @voice_xp_claim.after_loop
    async def before_voice_xp_claim(self) -> None:
        if self.voice_xp_claim.failed():
            logger.warning("VC経験値ループが失敗したため再起動します。")
            await self.bot.wait_until_ready()
            self.voice_xp_claim.restart()


def register_leveling_feature(bot: AsteroidBot) -> None:
    register_leveling_commands(bot)
    register_shard_commands(bot)
    register_power_commands(bot)
    register_leveling_admin_commands(bot)
    register_setup_command(bot, claim_voice_xp_button)


async def setup(bot: AsteroidBot) -> None:
    register_leveling_feature(bot)
    await bot.add_cog(LevelingSystemCore(bot))

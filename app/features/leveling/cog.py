from __future__ import annotations

import datetime
import random
from logging import getLogger
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from app.common.command_groups import register_setup_command
from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.discord_types import as_messageable
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    build_power_ranking_embed,
    build_shard_ranking_embed,
)
from app.features.leveling.commands.admin_command import register_leveling_admin_commands
from app.features.leveling.commands.command import register_leveling_commands
from app.features.leveling.commands.power_command import register_power_commands
from app.features.leveling.commands.shard_command import register_shard_commands
from app.features.leveling.message_handler import LevelingMessageHandler
from app.features.leveling.monthly import run_monthly_ranking
from app.features.leveling.setup_command import claim_voice_xp_button
from app.features.leveling.views import ClaimVoiceXP

logger = getLogger(__name__)
TOKYO_TZ = ZoneInfo("Asia/Tokyo")


class LevelingSystemCore(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.message_handler = LevelingMessageHandler(bot)
        self.ranking_board_messages: list[discord.Message] = []
        self.voice_xp_claim.start()
        self.delete_expired_xp_boosts.start()
        self.update_ranking_board.start()
        self.monthly_ranking.start()

    async def cog_unload(self) -> None:
        self.voice_xp_claim.cancel()
        self.delete_expired_xp_boosts.cancel()
        self.update_ranking_board.cancel()
        self.monthly_ranking.cancel()

    async def cleanup_on_shutdown(self) -> None:
        await self._cleanup_ranking_board_messages()

    async def cog_load(self) -> None:
        self.bot.add_view(ClaimVoiceXP(self.bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
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
            f"VC経験値ループを実行しました: guild_count={len(self.bot.guilds)} "
            f"scanned_channel_count={scanned_channel_count} rewarded_member_count={rewarded_member_count}"
        )

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
        monthly_powers = await self.bot.db.monthly_powers.get_monthly_power_ranking(limit=10)
        star_grades = await self.bot.db.star_grades.get_star_grade_ranking(limit=10)
        base_monthly = discord.Embed(
            title="月間ランキング",
            description="月間ランキング 現在のTOP10\n\n"
            f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
            f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
            f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
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
        if len(self.ranking_board_messages) == 0:
            await self._send_ranking_board_message(embeds=[shard_embed[0], monthly_embed[0]])
            logger.info("ランキングボードメッセージが存在しなかったため再作成しました。")
            return
        for ranking_board_message in list(self.ranking_board_messages):
            try:
                await ranking_board_message.edit(embeds=[shard_embed[0], monthly_embed[0]])
            except discord.NotFound:
                self.ranking_board_messages.remove(ranking_board_message)
                logger.warning(
                    f"ランキングボードメッセージが見つからなかったため管理対象から削除しました: "
                    f"message_id={ranking_board_message.id}"
                )
            except discord.HTTPException as error:
                logger.warning(
                    f"ランキングボードの更新に失敗しました。次回のループで再試行します: "
                    f"message_id={ranking_board_message.id} status={error.status} code={error.code}"
                )
        if len(self.ranking_board_messages) == 0:
            await self._send_ranking_board_message(embeds=[shard_embed[0], monthly_embed[0]])
            logger.warning("ランキングボードメッセージが削除されていたため再作成しました。")
        logger.debug(f"ランキングボードを更新しました: message_count={len(self.ranking_board_messages)}")

    @update_ranking_board.before_loop
    async def setup_ranking_board(self) -> None:
        await self.bot.wait_until_ready()
        await self._send_ranking_board_message(
            embeds=[discord.Embed(title="ランキングボード", description="更新待機中", color=AsteroidColor.INFO)]
        )

    @update_ranking_board.after_loop
    async def cleanup_ranking_board(self) -> None:
        if self.update_ranking_board.is_being_cancelled():
            await self._cleanup_ranking_board_messages()

    async def _send_ranking_board_message(self, embeds: list[discord.Embed]) -> None:
        channel = self.bot.get_channel(self.bot.config.leveling.ranking_board_channel_id)
        messageable_channel = as_messageable(channel)
        if messageable_channel is None:
            logger.warning(
                f"ランキングボード送信先チャンネルが見つかりませんでした: "
                f"channel_id={self.bot.config.leveling.ranking_board_channel_id}"
            )
            return
        message = await messageable_channel.send(embeds=embeds)
        self.ranking_board_messages.append(message)
        logger.info(
            f"ランキングボードを初期化しました: channel_id={getattr(channel, 'id', None)} message_id={message.id}"
        )

    async def _cleanup_ranking_board_messages(self) -> None:
        deleted_count = 0
        for message in self.ranking_board_messages:
            try:
                await message.delete()
                deleted_count += 1
            except discord.HTTPException:
                pass
        self.ranking_board_messages = []
        if deleted_count > 0:
            logger.info(f"ランキングボードメッセージを削除しました: count={deleted_count}")

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

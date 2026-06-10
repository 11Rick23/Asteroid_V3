from __future__ import annotations

import random
from logging import getLogger
from time import time

import discord

from app.core.bot import AsteroidBot

from .action_power import parse_action_power_command
from .build_send_message import send_grade_up_message, send_prestige_announce, send_prestige_up_message
from .manage_reward_role import sync_grade_prestige_role

logger = getLogger(__name__)


class LevelingMessageHandler:
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.cooldown: dict[int, float] = {}

    async def handle(self, message: discord.Message) -> None:
        self.bot.remember_message(message)
        if await self._try_action_power_command(message):
            return
        if (
            message.author.bot
            or message.guild is None
            or message.guild.id != self.bot.config.discord.guild_id
            or not isinstance(message.author, discord.Member)
        ):
            return
        cooldown_time = self.bot.config.leveling.message_cooldown
        if message.author.id in self.cooldown and self.cooldown[message.author.id] + cooldown_time >= time():
            logger.debug(
                f"レベリング加算をクールダウンでスキップしました: guild_id={message.guild.id} "
                f"channel_id={message.channel.id} user_id={message.author.id}"
            )
            return
        self.cooldown[message.author.id] = time()
        increase = random.randint(
            self.bot.config.leveling.min_xp_per_message,
            self.bot.config.leveling.max_xp_per_message,
        )
        if message.channel.type == discord.ChannelType.voice:
            increase = int(increase * self.bot.config.leveling.voice_xp_adjust)
        boost_increase = await self._calculate_boost(message.guild, message.author, increase)
        reward = await self.bot.db.leveling.apply_message_reward(message.author.id, increase, boost_increase)
        if reward.prestige_amount > 0:
            await send_prestige_up_message(
                message.channel,
                message.author,
                reward.star_grade.prestige,
                reward.prestige_amount,
            )
            await send_prestige_announce(self.bot, message.author, reward.star_grade.prestige)
            logger.debug(
                f"レベリングでプレステージ昇格が発生しました: guild_id={message.guild.id} "
                f"channel_id={message.channel.id} user_id={message.author.id} "
                f"prestige={reward.star_grade.prestige} amount={reward.prestige_amount}"
            )
        elif reward.grade_up_amount > 0:
            await send_grade_up_message(
                message.channel,
                message.author,
                reward.star_grade.grade,
                reward.grade_up_amount,
            )
            logger.debug(
                f"レベリングでグレード昇格が発生しました: guild_id={message.guild.id} "
                f"channel_id={message.channel.id} user_id={message.author.id} "
                f"grade={reward.star_grade.grade} amount={reward.grade_up_amount}"
            )
        await sync_grade_prestige_role(self.bot, message.author, reward.star_grade)

    async def _try_action_power_command(self, message: discord.Message) -> bool:
        if (
            message.guild is None
            or message.guild.id != self.bot.config.discord.guild_id
            or not message.author.bot
            or self.bot.config.leveling.action_power_channel_id == 0
            or message.channel.id != self.bot.config.leveling.action_power_channel_id
        ):
            return False
        command = parse_action_power_command(message.content)
        if command is None:
            return False
        user_id, value = command
        if message.guild.get_member(user_id) is None:
            logger.debug(f"アクションパワー加算をスキップしました: guild_id={message.guild.id} user_id={user_id}")
            return False
        await self.bot.db.leveling.add_action_power(user_id, value)
        try:
            await message.add_reaction("✅")
        except discord.HTTPException:
            pass
        logger.debug(
            f"アクションパワーコマンドを処理しました: guild_id={message.guild.id} "
            f"channel_id={message.channel.id} user_id={user_id} value={value}"
        )
        return True

    async def _calculate_boost(self, guild: discord.Guild, member: discord.Member, increase: int) -> int:
        total_boost_amount = 0.0
        for xp_boost in await self.bot.db.xp_boosts.get_xp_boosts():
            if guild.get_role(xp_boost.role_id) in member.roles:
                total_boost_amount += xp_boost.boost_amount / 100
        if total_boost_amount < 1:
            total_boost_amount += 1
        return int(increase * total_boost_amount) - increase

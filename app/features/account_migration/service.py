from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field, replace
from logging import getLogger

import discord

from app.core.bot import AsteroidBot
from app.database.account_migration import AccountState, MigrationOptions, PendingState, merge_leveling
from app.database.leveling_state import PowerState, ShardState

from . import messages
from .discord_state import DiscordState, prepare_discord
from .presentation import MigrationStatusView

logger = getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    source: AccountState
    target: AccountState
    options: MigrationOptions
    discord: DiscordState
    names: dict[int, str] = field(default_factory=dict, compare=False)

    def detail_file(self) -> discord.File:
        content = messages.details(self.source, self.target, self.discord, self.options, self.names)
        return discord.File(io.BytesIO(content.encode("utf-8")), filename="account-migration.txt")


def selected_state(state: AccountState, options: MigrationOptions) -> AccountState:
    return replace(
        state,
        shards=state.shards if options.leveling else ShardState(),
        powers=state.powers if options.leveling else PowerState(),
        pending=state.pending if options.leveling else PendingState(),
        birthday=state.birthday if options.birthday else None,
        saved_roles=state.saved_roles if options.roles else (),
    )


class MigrationService:
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot

    async def preview(
        self, guild: discord.Guild, source: discord.User, target_id: int, options: MigrationOptions
    ) -> MigrationPlan:
        if not self.bot.is_operating_guild(guild):
            raise ValueError("accounts")
        if not any((options.leveling, options.roles, options.birthday, options.free_category)):
            raise ValueError("disabled")
        if options.leveling and not self.bot.config.features.leveling:
            raise ValueError("leveling_disabled")
        source_data, target_data = await self.bot.db.account_migration.read_pair(source.id, target_id)
        if options.leveling:
            merge_leveling(source_data, target_data)
        discord_plan = await prepare_discord(
            guild, source, target_id, source_data, options, self.bot.config.free_category
        )
        if not (
            options.leveling
            and (
                source_data.shards.total
                or any(
                    (
                        source_data.powers.text,
                        source_data.powers.voice,
                        source_data.powers.action,
                        source_data.pending.voice_shard,
                        source_data.pending.bonus_shard,
                        source_data.pending.voice_power,
                    )
                )
            )
            or options.birthday
            and source_data.birthday
            or discord_plan.state.transferable_roles
            or discord_plan.state.skipped_roles
            or any(item.source is not None for item in discord_plan.state.permissions)
        ):
            raise ValueError("empty")
        names = {source.id: source.display_name, target_id: discord_plan.target.display_name}
        for role_id in set(discord_plan.state.source_roles) | set(discord_plan.state.target_roles):
            role = guild.get_role(role_id)
            if role is not None:
                names[role_id] = role.name
        names.update({channel_id: channel.name for channel_id, channel in discord_plan.channels.items()})
        return MigrationPlan(source_data, target_data, options, discord_plan.state, names)

    async def execute(
        self,
        guild: discord.Guild,
        source: discord.User,
        plan: MigrationPlan,
        record: discord.Message,
        actor_id: int,
    ) -> str:
        if not self.bot.is_operating_guild(guild) or record.guild is None or record.guild.id != guild.id:
            raise ValueError("accounts")
        repository = self.bot.db.account_migration
        async with self.bot.db.leveling.user_updates(plan.source.user_id, plan.target.user_id):
            async with self.bot.db.session() as session:
                # ID順で行ロックを取得し、逆方向の移行でもロック順を揃える。
                data = {
                    user_id: await repository.read(session, user_id, lock=True)
                    for user_id in sorted((plan.source.user_id, plan.target.user_id))
                }
                current_source, current_target = data[plan.source.user_id], data[plan.target.user_id]
                if any(
                    selected_state(current, plan.options) != selected_state(expected, plan.options)
                    for current, expected in ((current_source, plan.source), (current_target, plan.target))
                ):
                    raise ValueError("stale")
                discord_plan = await prepare_discord(
                    guild, source, plan.target.user_id, current_source, plan.options, self.bot.config.free_category
                )
                if discord_plan.state != plan.discord:
                    raise ValueError("stale")
                # 記録できなければ変更を始めない。完了時に同じメッセージの状態を更新する。
                await record.edit(
                    view=MigrationStatusView(plan, actor_id, messages.PROCESSING, include_restore=True),
                    attachments=[plan.detail_file()],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                cancelled: asyncio.CancelledError | None = None
                try:
                    await discord_plan.apply()
                    merged_roles = tuple(sorted(set(plan.discord.target_roles) | set(plan.discord.transferable_roles)))
                    remaining = tuple(sorted(set(current_source.saved_roles) - set(plan.discord.moving_roles)))
                    await repository.apply(
                        session, current_source, current_target, plan.options, merged_roles, remaining
                    )
                except (Exception, asyncio.CancelledError) as exc:
                    if isinstance(exc, asyncio.CancelledError):
                        cancelled = exc
                    database_rolled_back = True
                    try:
                        await session.rollback()
                    except Exception:
                        database_rolled_back = False
                        logger.exception("アカウント移行のDB変更を復元できませんでした")
                    discord_rolled_back = await discord_plan.rollback()
                    rolled_back = database_rolled_back and discord_rolled_back
                    result = messages.FAILED if rolled_back else messages.ROLLBACK_FAILED
                    logger.exception(
                        "アカウント移行に失敗しました: source_id=%s target_id=%s rollback=%s",
                        source.id,
                        plan.target.user_id,
                        rolled_back,
                    )
                else:
                    try:
                        await session.commit()
                    except (Exception, asyncio.CancelledError) as exc:
                        if isinstance(exc, asyncio.CancelledError):
                            cancelled = exc
                        # COMMITの通信切断は成否を断定できないため、Discordだけを巻き戻さない。
                        logger.exception(
                            "アカウント移行のcommit結果が不明です: source_id=%s target_id=%s",
                            source.id,
                            plan.target.user_id,
                        )
                        result = messages.COMMIT_UNCERTAIN
                    else:
                        result = messages.COMPLETED
                        logger.info(
                            "アカウント移行が完了しました: command=/migrate guild_id=%s actor_id=%s "
                            "source_id=%s target_id=%s options=%s record_id=%s",
                            guild.id,
                            actor_id,
                            source.id,
                            plan.target.user_id,
                            plan.options,
                            record.id,
                        )
                try:
                    await record.edit(
                        view=MigrationStatusView(plan, actor_id, result, include_restore=True),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except discord.HTTPException:
                    logger.exception("アカウント移行記録の更新に失敗しました: message_id=%s", record.id)
                    if result == messages.COMPLETED:
                        return messages.RECORD_FAILED
                if cancelled is not None:
                    raise cancelled
                return result

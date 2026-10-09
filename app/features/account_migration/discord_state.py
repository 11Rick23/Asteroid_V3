from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from logging import getLogger
from typing import cast

import discord

from app.core.config import FreeCategoryConfig
from app.database.account_migration import AccountState, MigrationOptions

logger = getLogger(__name__)
PermissionPair = tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class ChannelPermissions:
    channel_id: int
    source: PermissionPair
    target: PermissionPair

    @property
    def migrated(self) -> PermissionPair:
        if self.source is None:
            return self.target
        source_allow, source_deny = self.source
        target_allow, target_deny = self.target or (0, 0)
        specified = source_allow | source_deny
        return source_allow | (target_allow & ~specified), source_deny | (target_deny & ~specified)


@dataclass(frozen=True, slots=True)
class DiscordState:
    source_roles: tuple[int, ...] = ()
    target_roles: tuple[int, ...] = ()
    transferable_roles: tuple[int, ...] = ()
    skipped_roles: tuple[int, ...] = ()
    permissions: tuple[ChannelPermissions, ...] = ()

    @property
    def moving_roles(self) -> tuple[int, ...]:
        return tuple(role_id for role_id in self.transferable_roles if role_id not in self.target_roles)

    @property
    def shared_roles(self) -> tuple[int, ...]:
        return tuple(role_id for role_id in self.source_roles if role_id in self.target_roles)


def member_overwrite(channel: discord.TextChannel, user_id: int) -> PermissionPair:
    for target, value in channel.overwrites.items():
        if target.id == user_id and not isinstance(target, discord.Role):
            allow, deny = value.pair()
            return allow.value, deny.value
    return None


async def fetch_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


@dataclass(slots=True)
class DiscordMigration:
    guild: discord.Guild
    source: discord.User | discord.Member
    target: discord.Member
    state: DiscordState
    channels: dict[int, discord.TextChannel]
    undo: list[Callable[[], Awaitable[object]]] = field(default_factory=list)

    async def apply(self) -> None:
        reason = f"account migration: {self.source.id} -> {self.target.id}"
        for role_id in self.state.moving_roles:
            role = self.guild.get_role(role_id)
            if role is None:
                raise ValueError("stale")
            self.undo.append(lambda role=role: self.target.remove_roles(role, reason=reason))
            await self.target.add_roles(role, reason=reason)
            if isinstance(self.source, discord.Member) and role_id in self.state.source_roles:
                source = self.source
                self.undo.append(lambda role=role, source=source: source.add_roles(role, reason=reason))
                await source.remove_roles(role, reason=reason)
        # discord.pyの実装はabc.Userも受け付けるが、型注釈はMember/Roleに限定されている。
        permission_source = cast(discord.Member, self.source)
        for value in self.state.permissions:
            channel = self.channels[value.channel_id]
            if value.migrated != value.target:
                self.undo.append(
                    lambda channel=channel, value=value: channel.set_permissions(
                        self.target, overwrite=to_overwrite(value.target), reason=reason
                    )
                )
                await channel.set_permissions(self.target, overwrite=to_overwrite(value.migrated), reason=reason)
            if value.source is not None:
                self.undo.append(
                    lambda channel=channel, value=value: channel.set_permissions(
                        permission_source, overwrite=to_overwrite(value.source), reason=reason
                    )
                )
                await channel.set_permissions(permission_source, overwrite=None, reason=reason)

    async def rollback(self) -> bool:
        complete = True
        for undo in reversed(self.undo):
            try:
                await undo()
            except Exception:
                complete = False
                logger.exception("アカウント移行のDiscord変更を復元できませんでした")
        return complete


def to_overwrite(value: PermissionPair) -> discord.PermissionOverwrite | None:
    return (
        None
        if value is None
        else discord.PermissionOverwrite.from_pair(discord.Permissions(value[0]), discord.Permissions(value[1]))
    )


async def prepare_discord(
    guild: discord.Guild,
    source_user: discord.User,
    target_id: int,
    source_data: AccountState,
    options: MigrationOptions,
    config: FreeCategoryConfig,
) -> DiscordMigration:
    source = await fetch_member(guild, source_user.id)
    target = await fetch_member(guild, target_id)
    if target is None or target.bot or source_user.bot or source_user.id == target_id:
        raise ValueError("accounts")
    source_roles: tuple[int, ...] = ()
    target_roles: tuple[int, ...] = ()
    transferable: list[int] = []
    skipped: list[int] = []
    if options.roles:
        source_roles = (
            tuple(sorted(role.id for role in source.roles if not role.is_default()))
            if source
            else source_data.saved_roles
        )
        target_roles = tuple(sorted(role.id for role in target.roles if not role.is_default()))
        for role_id in source_roles:
            role = guild.get_role(role_id)
            if (
                role is None
                or role.managed
                or role.is_default()
                or not role.is_assignable()
                or not guild.me.guild_permissions.manage_roles
            ):
                skipped.append(role_id)
            else:
                transferable.append(role_id)
    channels: dict[int, discord.TextChannel] = {}
    permissions = []
    if options.free_category:
        category_ids = {
            config.free_category_id,
            config.minor_category_id,
            config.hall_of_fame_category_id,
            config.fc_archive_category_id,
        } - {0}
        for channel in await guild.fetch_channels():
            if not isinstance(channel, discord.TextChannel) or channel.category_id not in category_ids:
                continue
            before = member_overwrite(channel, source_user.id)
            after = member_overwrite(channel, target_id)
            if before is None:
                continue
            if not channel.permissions_for(guild.me).manage_roles:
                raise ValueError("permissions")
            channels[channel.id] = channel
            permissions.append(ChannelPermissions(channel.id, before, after))
    state = DiscordState(
        source_roles,
        target_roles,
        tuple(transferable),
        tuple(skipped),
        tuple(sorted(permissions, key=lambda item: item.channel_id)),
    )
    return DiscordMigration(guild, source or source_user, target, state, channels)

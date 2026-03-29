from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import discord

from app.common.utils import generate_timestamp


@dataclass
class UserRoleData:
    user_id: int
    role_id: int
    created_at: datetime
    updated_at: datetime


class UserRoles:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'user_roles'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS user_roles (user_id BIGINT UNSIGNED, role_id BIGINT UNSIGNED,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP,"
                    "PRIMARY KEY (user_id, role_id))"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS user_roles")
                await conn.commit()

    async def get_user_roles(self, user_id: int) -> list[UserRoleData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM user_roles WHERE user_id = %s", (user_id,))
                raw_roles = await cur.fetchall()
                await conn.commit()
                return [UserRoleData(*role) for role in raw_roles]

    async def save_user_roles(self, member: discord.Member) -> None:
        await self.delete_user_roles(member.id)
        data = []
        ignored_save_role_ids = self.db.config.roles.ignored_save_role_id_list
        for role in member.roles:
            if (
                role == member.guild.default_role
                or role >= member.guild.me.top_role
                or role.id in ignored_save_role_ids
            ):
                continue
            data.append((member.id, role.id))
        if not data:
            return
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", data)
                await conn.commit()

    async def delete_user_roles(self, user_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
                await conn.commit()

    async def delete_user_role(self, user_id: int, role_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM user_roles WHERE user_id = %s AND role_id = %s", (user_id, role_id))
                await conn.commit()

    async def restore_user_roles(self, member: discord.Member) -> int:
        roles_data = await self.get_user_roles(member.id)
        append_roles: list[discord.Role] = []
        for role_data in roles_data:
            role = member.guild.get_role(role_data.role_id)
            if role is None:
                await self.delete_user_role(member.id, role_data.role_id)
                continue
            if role < member.guild.me.top_role:
                append_roles.append(role)
        if append_roles:
            await member.add_roles(
                *append_roles,
                reason=f"[{generate_timestamp()}] ロール復元機能により付与されました。",
                atomic=False,
            )
        return len(append_roles)

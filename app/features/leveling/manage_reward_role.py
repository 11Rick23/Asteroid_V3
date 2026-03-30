from __future__ import annotations

import discord

from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot
from app.core.config import GradeRoleReward, PrestigeRoleReward
from app.database.repositories.star_grades import StarGradeData


def get_member_grade_roles(grade: int, grade_roles: list[GradeRoleReward], stack: bool) -> tuple[list[int], list[int]]:
    if len(grade_roles) < 1:
        return [], []
    add_grade_roles = [role for role in grade_roles if role.grade <= grade]
    remove_grade_roles = [role for role in grade_roles if role.grade > grade]
    if stack:
        return [role.role_id for role in add_grade_roles], [role.role_id for role in remove_grade_roles]
    sorted_add_grade_roles = [
        role.role_id for role in sorted(add_grade_roles, key=lambda role: role.grade, reverse=True)
    ]
    return [sorted_add_grade_roles[0]], sorted_add_grade_roles[1:] + [role.role_id for role in remove_grade_roles]


def get_member_prestige_roles(
    prestige: int, prestige_roles: list[PrestigeRoleReward], stack: bool
) -> tuple[list[int], list[int]]:
    if len(prestige_roles) < 1:
        return [], []
    add_prestige_roles = [role for role in prestige_roles if role.prestige <= prestige]
    remove_prestige_roles = [role for role in prestige_roles if role.prestige > prestige]
    if stack:
        return [role.role_id for role in add_prestige_roles], [role.role_id for role in remove_prestige_roles]
    sorted_add_prestige_roles = [
        role.role_id for role in sorted(add_prestige_roles, key=lambda role: role.prestige, reverse=True)
    ]
    return (
        [sorted_add_prestige_roles[0]] if len(sorted_add_prestige_roles) > 0 else [],
        (sorted_add_prestige_roles[1:] if len(sorted_add_prestige_roles) > 0 else [])
        + [role.role_id for role in remove_prestige_roles],
    )


async def sync_grade_prestige_role(bot: AsteroidBot, member: discord.Member, star_grade_data: StarGradeData) -> None:
    add_grade_roles, remove_grade_roles = get_member_grade_roles(
        star_grade_data.grade,
        bot.config.leveling.grade_roles_id_list,
        bot.config.leveling.stack_grade_role,
    )
    add_prestige_roles, remove_prestige_roles = get_member_prestige_roles(
        star_grade_data.prestige,
        bot.config.leveling.prestige_roles_id_list,
        bot.config.leveling.stack_prestige_role,
    )
    add_roles = []
    remove_roles = []
    for role_id in add_grade_roles + add_prestige_roles:
        role = member.guild.get_role(role_id)
        if role is not None and role not in member.roles:
            add_roles.append(role)
    for role_id in remove_grade_roles + remove_prestige_roles:
        role = member.guild.get_role(role_id)
        if role is not None and role in member.roles:
            remove_roles.append(role)
    if add_roles:
        await member.add_roles(
            *add_roles,
            reason=f"[{generate_timestamp()}] グレード・プレステージロール同期機能により付与されました",
            atomic=False,
        )
    if remove_roles:
        await member.remove_roles(
            *remove_roles,
            reason=f"[{generate_timestamp()}] 自動グレード・プレステージロール同期機能により剥奪されました",
            atomic=False,
        )

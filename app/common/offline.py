from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import discord

from app.common.constants import AsteroidColor


@dataclass(frozen=True, slots=True)
class OfflineInfo:
    reason: str
    planned_period: str

    @classmethod
    def from_signal(cls, signal_name: str) -> OfflineInfo:
        return cls(
            reason=f"{signal_name} シグナルによる強制停止",
            planned_period="未定",
        )


class ApplicationInfoProvider(Protocol):
    async def application_info(self) -> discord.AppInfo: ...


async def get_emergency_contact_mentions(provider: ApplicationInfoProvider) -> tuple[str, ...]:
    application_info = await provider.application_info()
    if application_info.team is not None and application_info.team.members:
        return tuple(member.mention for member in application_info.team.members)
    return (application_info.owner.mention,)


def build_offline_embed(info: OfflineInfo, emergency_contact_mentions: Sequence[str]) -> discord.Embed:
    contacts = "\n".join(emergency_contact_mentions)
    embed = discord.Embed(
        title="BOT は現在オフラインです",
        color=AsteroidColor.WARNING,
    )
    embed.add_field(name="理由", value=info.reason, inline=False)
    embed.add_field(name="予定期間", value=info.planned_period, inline=False)
    embed.add_field(name="緊急連絡先", value=contacts, inline=False)
    return embed

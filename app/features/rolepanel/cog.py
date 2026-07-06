from __future__ import annotations

from app.core.bot import AsteroidBot

from .admin_views import RolePanelAdminRoleEditView, RolePanelAdminRoleSelect
from .commands import register_rolepanel_commands, rolepanel_group
from .runtime import RolePanelCog
from .service import get_rolepanel_service

__all__ = [
    "RolePanelAdminRoleEditView",
    "RolePanelAdminRoleSelect",
    "RolePanelCog",
    "rolepanel_group",
]


async def setup(bot: AsteroidBot) -> None:
    get_rolepanel_service(bot)
    register_rolepanel_commands(bot)
    await bot.add_cog(RolePanelCog(bot))

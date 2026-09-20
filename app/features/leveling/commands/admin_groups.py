from __future__ import annotations

from discord import app_commands

from app.common.permissions import ADMINISTRATOR_PERMISSIONS
from app.features.leveling.messages import admin as messages

leveling_admin_group = app_commands.Group(
    name="leveling",
    description=messages.ADMIN_GROUP_DESCRIPTION,
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)
admin_shard_group = app_commands.Group(
    name="shard",
    description=messages.ADMIN_SHARD_GROUP_DESCRIPTION,
    parent=leveling_admin_group,
)
admin_power_group = app_commands.Group(
    name="power",
    description=messages.ADMIN_POWER_GROUP_DESCRIPTION,
    parent=leveling_admin_group,
)

from __future__ import annotations

from .given_stars import GivenStars
from .leveling import LevelingTransactions
from .monthly_action_powers import MonthlyActionPowers
from .monthly_powers import MonthlyPowers
from .role_panel import RolePanel
from .star_grades import StarGrades
from .starred_messages import StarredMessages
from .user_birthdays import UserBirthdays
from .user_roles import UserRoles
from .voice_xp_limits import VoiceXPLimits
from .xp_boosts import XPBoosts


class DatabaseRepositories:
    def __init__(self) -> None:
        self.user_roles = UserRoles(self)
        self.given_stars = GivenStars(self)
        self.leveling = LevelingTransactions(self)
        self.starred_messages = StarredMessages(self)
        self.xp_boosts = XPBoosts(self)
        self.star_grades = StarGrades(self)
        self.voice_xp_limits = VoiceXPLimits(self)
        self.monthly_action_powers = MonthlyActionPowers(self)
        self.monthly_powers = MonthlyPowers(self)
        self.user_birthdays = UserBirthdays(self)
        self.role_panel = RolePanel(self)

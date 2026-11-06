"""新schemaは明示import時だけ登録し、旧BotのBaseへ登録しない。"""

from .accounts import Account, Boost, Channel, Installation
from .audit import Correction, CorrectionChange, CorrectionRoleChoice, EventOwnershipMove, Operation
from .base import LevelingBase
from .events import Event, EventChannel, EventPeriod, MessageReceipt
from .migration import ImportItem, MigrationItem, MigrationRun
from .outbox import AnnouncementPart, MonthlyQualification, OutboxJob, PermanentAward, RoleDesire
from .periods import PeriodChannel, PeriodChannelUser, PeriodRow, PeriodUser
from .rankings import RankingRevision, RankingRow, SnapshotChannelInput, SnapshotUserInput
from .voice import Claim, ClaimItem, VoiceGrant, VoicePending, VoiceSegmentRow, VoiceState

__all__ = [
    "Account",
    "Boost",
    "Channel",
    "Installation",
    "Correction",
    "CorrectionChange",
    "CorrectionRoleChoice",
    "EventOwnershipMove",
    "Operation",
    "LevelingBase",
    "Event",
    "EventChannel",
    "EventPeriod",
    "MessageReceipt",
    "ImportItem",
    "MigrationItem",
    "MigrationRun",
    "AnnouncementPart",
    "MonthlyQualification",
    "OutboxJob",
    "PermanentAward",
    "RoleDesire",
    "PeriodChannel",
    "PeriodChannelUser",
    "PeriodRow",
    "PeriodUser",
    "RankingRevision",
    "RankingRow",
    "SnapshotChannelInput",
    "SnapshotUserInput",
    "Claim",
    "ClaimItem",
    "VoiceGrant",
    "VoicePending",
    "VoiceSegmentRow",
    "VoiceState",
]

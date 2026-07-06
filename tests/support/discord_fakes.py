from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FakeDiscordConfig:
    guild_id: int


@dataclass(slots=True)
class FakeConfig:
    discord: FakeDiscordConfig


@dataclass(slots=True)
class FakeClient:
    guild_id: int

    @property
    def config(self) -> FakeConfig:
        return FakeConfig(discord=FakeDiscordConfig(guild_id=self.guild_id))


class FakeInteractionResponse:
    def __init__(self, *, done: bool = False) -> None:
        self._done = done
        self.sent_messages: list[dict[str, Any]] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: str | None = None, **kwargs: Any) -> None:
        self._done = True
        self.sent_messages.append({"content": content, **kwargs})


class FakeFollowup:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def send(self, content: str | None = None, **kwargs: Any) -> None:
        self.sent_messages.append({"content": content, **kwargs})


@dataclass(slots=True)
class FakeInteraction:
    client: object
    guild_id: int | None
    user: FakeUser = field(default_factory=lambda: FakeUser(100))
    channel_id: int | None = None
    guild: object | None = None
    response: FakeInteractionResponse = field(default_factory=FakeInteractionResponse)
    followup: FakeFollowup = field(default_factory=FakeFollowup)


@dataclass(slots=True)
class FakeUser:
    id: int
    mention: str | None = None

    def __post_init__(self) -> None:
        if self.mention is None:
            self.mention = f"<@{self.id}>"


@dataclass(slots=True)
class FakeRole:
    id: int
    position: int
    managed: bool = False

    @property
    def mention(self) -> str:
        return f"<@&{self.id}>"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, FakeRole):
            return NotImplemented
        return self.position < other.position


class FakeGuild:
    def __init__(
        self,
        *,
        guild_id: int = 12345,
        roles: list[FakeRole] | None = None,
        bot_top_role: FakeRole | None = None,
    ) -> None:
        self.id = guild_id
        self.default_role = FakeRole(id=0, position=0)
        self.me = type("FakeMe", (), {"top_role": bot_top_role or FakeRole(id=999, position=999)})()
        self._roles = {role.id: role for role in roles or []}

    def get_role(self, role_id: int) -> FakeRole | None:
        return self._roles.get(role_id)


class FakeMember:
    def __init__(
        self,
        *,
        member_id: int = 100,
        guild: FakeGuild,
        roles: list[FakeRole] | None = None,
        premium_since: object | None = None,
        name: str = "member",
        bot: bool = False,
    ) -> None:
        self.id = member_id
        self.name = name
        self.display_name = name
        self.mention = f"<@{member_id}>"
        self.bot = bot
        self.guild = guild
        self.roles = roles or []
        self.premium_since = premium_since
        self.added_roles: list[FakeRole] = []
        self.removed_roles: list[FakeRole] = []

    async def add_roles(self, *roles: FakeRole, **_: Any) -> None:
        self.added_roles.extend(roles)

    async def remove_roles(self, *roles: FakeRole, **_: Any) -> None:
        self.removed_roles.extend(roles)


@dataclass(slots=True)
class FakePanelComponent:
    id: int
    children: list[object] = field(default_factory=list)


class FakePanelMessage:
    def __init__(
        self,
        *,
        message_id: int,
        author_id: int,
        components: list[object] | None = None,
    ) -> None:
        self.id = message_id
        self.author = FakeUser(author_id)
        self.components = components or []
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)


class FakeTextChannel:
    def __init__(
        self,
        *,
        channel_id: int,
        latest_message: FakePanelMessage | None = None,
    ) -> None:
        self.id = channel_id
        self.latest_message = latest_message
        self.sent_messages: list[dict[str, Any]] = []
        self.sent_message_id = 1000

    async def fetch_message(self, message_id: int) -> FakePanelMessage | None:
        if self.latest_message is not None and self.latest_message.id == message_id:
            return self.latest_message
        return None

    async def send(self, **kwargs: Any) -> FakePanelMessage:
        self.sent_messages.append(kwargs)
        message = FakePanelMessage(message_id=self.sent_message_id, author_id=0)
        self.sent_message_id += 1
        self.latest_message = message
        return message

    async def history(self, *, limit: int = 1):
        if limit and self.latest_message is not None:
            yield self.latest_message


class FakePanelBot:
    def __init__(self, *, channel: FakeTextChannel, user_id: int = 42, operating: bool = True) -> None:
        self.user = FakeUser(user_id)
        self.channel = channel
        self.operating = operating
        self.fetch_count = 0

    def get_channel(self, channel_id: int) -> FakeTextChannel | None:
        return self.channel if channel_id == self.channel.id else None

    async def fetch_channel(self, channel_id: int) -> FakeTextChannel:
        self.fetch_count += 1
        return self.channel

    def is_operating_channel(self, channel: object) -> bool:
        return self.operating and channel is self.channel

    async def application_info(self) -> object:
        return type(
            "FakeApplicationInfo",
            (),
            {
                "team": None,
                "owner": FakeUser(777),
            },
        )()

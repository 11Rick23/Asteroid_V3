from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.database.models.starred_messages import StarredMessageModel
from app.database.repositories.starred_messages import StarredMessageData, StarredMessages
from app.features.starboard import cog as starboard_cog


class DummyAsyncSessionContext:
    def __init__(self, session: object) -> None:
        self.session = session

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class DummyScalarSession:
    def __init__(self, result: list[StarredMessageModel]) -> None:
        self.result = result
        self.statement = None

    async def scalars(self, statement):
        self.statement = statement
        return self.result


class DummyGetSession:
    def __init__(self, model: StarredMessageModel | None) -> None:
        self.model = model
        self.get_calls: list[tuple[type[object], int]] = []
        self.commit_count = 0

    async def get(self, model_class: type[object], message_id: int) -> StarredMessageModel | None:
        self.get_calls.append((model_class, message_id))
        return self.model

    async def commit(self) -> None:
        self.commit_count += 1


def build_starred_message_data(*, starred_message_id: int, starboard_message_id: int) -> StarredMessageData:
    now = datetime.now(UTC)
    return StarredMessageData(
        starred_message_id=starred_message_id,
        starboard_message_id=starboard_message_id,
        star_amount=5,
        user_id=10,
        starred_message_channel_id=20,
        created_at=now,
        updated_at=now,
    )


def build_http_exception(exception_cls: type[discord.HTTPException], *, status: int, reason: str, text: str):
    response = SimpleNamespace(status=status, reason=reason)
    return exception_cls(cast(Any, response), {"message": text, "code": 0})


@pytest.mark.asyncio
async def test_get_all_starred_messages_orders_by_created_at_then_message_id() -> None:
    first = StarredMessageModel(
        starred_message_id=1,
        starboard_message_id=101,
        star_amount=5,
        user_id=10,
        starred_message_channel_id=20,
    )
    second = StarredMessageModel(
        starred_message_id=2,
        starboard_message_id=102,
        star_amount=6,
        user_id=11,
        starred_message_channel_id=21,
    )
    session = DummyScalarSession([first, second])
    repository = StarredMessages(SimpleNamespace(session=lambda: DummyAsyncSessionContext(session)))

    result = await repository.get_all_starred_messages()

    assert [item.starred_message_id for item in result] == [1, 2]
    assert "ORDER BY starred_messages.created_at ASC, starred_messages.starred_message_id ASC" in str(
        session.statement
    )


@pytest.mark.asyncio
async def test_set_starboard_message_id_updates_only_target_field() -> None:
    model = StarredMessageModel(
        starred_message_id=1,
        starboard_message_id=101,
        star_amount=5,
        user_id=10,
        starred_message_channel_id=20,
    )
    session = DummyGetSession(model)
    repository = StarredMessages(SimpleNamespace(session=lambda: DummyAsyncSessionContext(session)))

    await repository.set_starboard_message_id(1, 202)

    assert session.get_calls == [(StarredMessageModel, 1)]
    assert model.starboard_message_id == 202
    assert model.star_amount == 5
    assert session.commit_count == 1


class DummyResponse:
    def __init__(self) -> None:
        self.defer_calls: list[dict[str, object]] = []

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.defer_calls.append({"ephemeral": ephemeral, "thinking": thinking})


class DummyFollowup:
    def __init__(self) -> None:
        self.send_calls: list[tuple[str, bool]] = []

    async def send(self, content: str, *, ephemeral: bool = False) -> None:
        self.send_calls.append((content, ephemeral))


class DummyAuthor:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class DummyMessage:
    def __init__(self, message_id: int, author_id: int, content: str, embeds: list[discord.Embed]) -> None:
        self.id = message_id
        self.author = DummyAuthor(author_id)
        self.content = content
        self.embeds = embeds


class DummyChannel:
    def __init__(
        self,
        channel_id: int,
        *,
        bot_user_id: int | None = None,
        fetch_messages: dict[int, DummyMessage] | None = None,
        history_messages: list[DummyMessage] | None = None,
        send_exception: Exception | None = None,
    ) -> None:
        self.id = channel_id
        self._bot_user_id = bot_user_id
        self._fetch_messages = fetch_messages or {}
        self._history_messages = history_messages or []
        self._send_exception = send_exception
        self.sent_messages: list[DummyMessage] = []

    async def fetch_message(self, message_id: int) -> DummyMessage:
        if message_id not in self._fetch_messages:
            raise build_http_exception(discord.NotFound, status=404, reason="Not Found", text="missing")
        return self._fetch_messages[message_id]

    async def send(self, *, content: str, embeds: list[discord.Embed]) -> DummyMessage:
        if self._send_exception is not None:
            raise self._send_exception
        message = DummyMessage(9000 + len(self.sent_messages) + 1, self._bot_user_id or 0, content, embeds)
        self.sent_messages.append(message)
        return message

    def history(self, *, limit=None):
        async def iterator():
            for message in self._history_messages:
                yield message

        return iterator()


class DummyGuild:
    def __init__(self, channels: dict[int, DummyChannel]) -> None:
        self.id = 123
        self._channels = channels

    def get_channel(self, channel_id: int) -> DummyChannel | None:
        return self._channels.get(channel_id)


class DummyStarredMessagesRepository:
    def __init__(self, entries: list[StarredMessageData]) -> None:
        self.entries = entries
        self.get_all_calls = 0
        self.updated_ids: list[tuple[int, int]] = []
        self.deleted_ids: list[int] = []

    async def get_all_starred_messages(self) -> list[StarredMessageData]:
        self.get_all_calls += 1
        return list(self.entries)

    async def set_starboard_message_id(self, message_id: int, starboard_message_id: int) -> None:
        self.updated_ids.append((message_id, starboard_message_id))

    async def delete_starred_message(self, message_id: int) -> None:
        self.deleted_ids.append(message_id)


class DummyInteraction:
    def __init__(self, guild: DummyGuild, channel: DummyChannel) -> None:
        self.guild = guild
        self.channel = channel
        self.response = DummyResponse()
        self.followup = DummyFollowup()


@pytest.mark.asyncio
async def test_setup_starboard_recreates_messages_and_updates_database(monkeypatch: pytest.MonkeyPatch) -> None:
    source_channel = DummyChannel(
        111,
        fetch_messages={
            1001: DummyMessage(1001, 50, "old content", [discord.Embed(title="old embed")]),
        },
    )
    target_channel = DummyChannel(222, bot_user_id=42)
    starred_messages = DummyStarredMessagesRepository(
        [build_starred_message_data(starred_message_id=1, starboard_message_id=1001)]
    )
    bot = SimpleNamespace(
        config=SimpleNamespace(starboard=SimpleNamespace(starboard_channel_id=222)),
        user=SimpleNamespace(id=42),
        db=SimpleNamespace(starred_messages=starred_messages),
    )
    interaction = DummyInteraction(DummyGuild({222: target_channel}), source_channel)
    monkeypatch.setattr(starboard_cog, "get_bot", lambda _: bot)

    await cast(Any, starboard_cog.setup_starboard.callback)(interaction)

    assert interaction.response.defer_calls == [{"ephemeral": True, "thinking": True}]
    assert starred_messages.updated_ids == [(1, 9001)]
    assert starred_messages.deleted_ids == []
    assert len(target_channel.sent_messages) == 1
    assert target_channel.sent_messages[0].content == "old content"
    assert target_channel.sent_messages[0].embeds[0].title == "old embed"
    assert interaction.followup.send_calls == [
        ("スターボード再作成が完了しました。\n対象件数: 1\n再作成件数: 1\n欠損削除件数: 0", True)
    ]


@pytest.mark.asyncio
async def test_setup_starboard_stops_when_destination_already_has_bot_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_channel = DummyChannel(111)
    target_channel = DummyChannel(222, history_messages=[DummyMessage(5001, 42, "existing", [])])
    starred_messages = DummyStarredMessagesRepository(
        [build_starred_message_data(starred_message_id=1, starboard_message_id=1001)]
    )
    bot = SimpleNamespace(
        config=SimpleNamespace(starboard=SimpleNamespace(starboard_channel_id=222)),
        user=SimpleNamespace(id=42),
        db=SimpleNamespace(starred_messages=starred_messages),
    )
    interaction = DummyInteraction(DummyGuild({222: target_channel}), source_channel)
    monkeypatch.setattr(starboard_cog, "get_bot", lambda _: bot)

    await cast(Any, starboard_cog.setup_starboard.callback)(interaction)

    assert starred_messages.get_all_calls == 0
    assert interaction.followup.send_calls == [
        ("新しいスターボードチャンネルに既に BOT の投稿があります。再実行はできません。", True)
    ]


@pytest.mark.asyncio
async def test_setup_starboard_deletes_missing_source_message_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_channel = DummyChannel(
        111,
        fetch_messages={
            1002: DummyMessage(1002, 50, "second", [discord.Embed(title="second embed")]),
        },
    )
    target_channel = DummyChannel(222, bot_user_id=42)
    starred_messages = DummyStarredMessagesRepository(
        [
            build_starred_message_data(starred_message_id=1, starboard_message_id=1001),
            build_starred_message_data(starred_message_id=2, starboard_message_id=1002),
        ]
    )
    bot = SimpleNamespace(
        config=SimpleNamespace(starboard=SimpleNamespace(starboard_channel_id=222)),
        user=SimpleNamespace(id=42),
        db=SimpleNamespace(starred_messages=starred_messages),
    )
    interaction = DummyInteraction(DummyGuild({222: target_channel}), source_channel)
    monkeypatch.setattr(starboard_cog, "get_bot", lambda _: bot)

    await cast(Any, starboard_cog.setup_starboard.callback)(interaction)

    assert starred_messages.deleted_ids == [1]
    assert starred_messages.updated_ids == [(2, 9001)]
    assert interaction.followup.send_calls == [
        ("スターボード再作成が完了しました。\n対象件数: 2\n再作成件数: 1\n欠損削除件数: 1", True)
    ]


@pytest.mark.asyncio
async def test_setup_starboard_rejects_same_source_and_target_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = DummyChannel(222)
    starred_messages = DummyStarredMessagesRepository([])
    bot = SimpleNamespace(
        config=SimpleNamespace(starboard=SimpleNamespace(starboard_channel_id=222)),
        user=SimpleNamespace(id=42),
        db=SimpleNamespace(starred_messages=starred_messages),
    )
    interaction = DummyInteraction(DummyGuild({222: channel}), channel)
    monkeypatch.setattr(starboard_cog, "get_bot", lambda _: bot)

    await cast(Any, starboard_cog.setup_starboard.callback)(interaction)

    assert starred_messages.get_all_calls == 0
    assert interaction.followup.send_calls == [
        ("実行チャンネルとスターボードチャンネルが同一です。別の旧スターボードチャンネルで実行してください。", True)
    ]


@pytest.mark.asyncio
async def test_setup_starboard_stops_when_destination_send_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    source_channel = DummyChannel(
        111,
        fetch_messages={
            1001: DummyMessage(1001, 50, "old content", [discord.Embed(title="old embed")]),
        },
    )
    target_channel = DummyChannel(
        222,
        bot_user_id=42,
        send_exception=build_http_exception(discord.Forbidden, status=403, reason="Forbidden", text="forbidden"),
    )
    starred_messages = DummyStarredMessagesRepository(
        [build_starred_message_data(starred_message_id=1, starboard_message_id=1001)]
    )
    bot = SimpleNamespace(
        config=SimpleNamespace(starboard=SimpleNamespace(starboard_channel_id=222)),
        user=SimpleNamespace(id=42),
        db=SimpleNamespace(starred_messages=starred_messages),
    )
    interaction = DummyInteraction(DummyGuild({222: target_channel}), source_channel)
    monkeypatch.setattr(starboard_cog, "get_bot", lambda _: bot)

    await cast(Any, starboard_cog.setup_starboard.callback)(interaction)

    assert starred_messages.updated_ids == []
    assert interaction.followup.send_calls == [
        (
            "新しいスターボードチャンネルへの送信権限がありません。処理を中断しました。\n"
            "対象件数: 1\n"
            "処理済み件数: 0\n"
            "再作成件数: 0\n"
            "欠損削除件数: 0",
            True,
        )
    ]


@pytest.mark.asyncio
async def test_setup_starboard_stops_when_destination_channel_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    source_channel = DummyChannel(111)
    starred_messages = DummyStarredMessagesRepository([])
    bot = SimpleNamespace(
        config=SimpleNamespace(starboard=SimpleNamespace(starboard_channel_id=222)),
        user=SimpleNamespace(id=42),
        db=SimpleNamespace(starred_messages=starred_messages),
    )
    interaction = DummyInteraction(DummyGuild({}), source_channel)
    monkeypatch.setattr(starboard_cog, "get_bot", lambda _: bot)

    await cast(Any, starboard_cog.setup_starboard.callback)(interaction)

    assert starred_messages.get_all_calls == 0
    assert interaction.followup.send_calls == [("スターボードチャンネル設定が不足しています。", True)]

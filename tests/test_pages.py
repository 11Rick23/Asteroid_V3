from __future__ import annotations

import discord
import pytest

from app.common.pages import Paginator


class DummyResponse:
    def __init__(self, *, done: bool):
        self._done = done
        self.send_calls: list[tuple[discord.Embed, object]] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, *, embed: discord.Embed, view: object) -> None:
        self.send_calls.append((embed, view))


class DummyFollowup:
    def __init__(self, *, message: object):
        self.message = message
        self.send_calls: list[tuple[discord.Embed, object, bool]] = []

    async def send(self, *, embed: discord.Embed, view: object, wait: bool = False) -> object:
        self.send_calls.append((embed, view, wait))
        return self.message


class DummyInteraction:
    def __init__(self, *, response_done: bool, original_message: object, followup_message: object):
        self.response = DummyResponse(done=response_done)
        self.followup = DummyFollowup(message=followup_message)
        self._original_message = original_message
        self.original_response_calls = 0

    async def original_response(self) -> object:
        self.original_response_calls += 1
        return self._original_message


@pytest.mark.asyncio
async def test_paginator_respond_returns_original_response_message() -> None:
    paginator = Paginator(pages=[discord.Embed(title="page")])
    original_message = object()
    interaction = DummyInteraction(
        response_done=False,
        original_message=original_message,
        followup_message=object(),
    )

    message = await paginator.respond(interaction)

    assert message is original_message
    assert len(interaction.response.send_calls) == 1
    assert interaction.original_response_calls == 1


@pytest.mark.asyncio
async def test_paginator_respond_returns_followup_message_when_response_done() -> None:
    paginator = Paginator(pages=[discord.Embed(title="page")])
    followup_message = object()
    interaction = DummyInteraction(
        response_done=True,
        original_message=object(),
        followup_message=followup_message,
    )

    message = await paginator.respond(interaction)

    assert message is followup_message
    assert len(interaction.followup.send_calls) == 1
    assert interaction.followup.send_calls[0][2] is True
    assert interaction.original_response_calls == 0

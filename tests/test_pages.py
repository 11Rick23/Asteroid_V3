from __future__ import annotations

from typing import cast

import discord
import pytest

from app.common.pages import Paginator, _PaginatorView


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


class DummyEditResponse:
    def __init__(self) -> None:
        self.edit_calls: list[tuple[discord.Embed, object]] = []

    async def edit_message(self, *, embed: discord.Embed, view: object) -> None:
        self.edit_calls.append((embed, view))


class DummyCallbackInteraction:
    def __init__(self) -> None:
        self.response = DummyEditResponse()


@pytest.mark.asyncio
async def test_paginator_respond_returns_original_response_message() -> None:
    paginator = Paginator(pages=[discord.Embed(title="page")])
    original_message = object()
    interaction = DummyInteraction(
        response_done=False,
        original_message=original_message,
        followup_message=object(),
    )

    message = await paginator.respond(cast(discord.Interaction, interaction))

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

    message = await paginator.respond(cast(discord.Interaction, interaction))

    assert message is followup_message
    assert len(interaction.followup.send_calls) == 1
    assert interaction.followup.send_calls[0][2] is True
    assert interaction.original_response_calls == 0


def test_paginator_hides_disabled_navigation_buttons_when_requested() -> None:
    paginator = Paginator(
        pages=[discord.Embed(title="page1"), discord.Embed(title="page2")],
        show_disabled=False,
    )
    view = _PaginatorView(
        paginator.pages,
        paginator.buttons,
        loop_pages=paginator.loop_pages,
        show_disabled=paginator.show_disabled,
    )

    assert [cast(discord.ui.Button, item).label for item in view.children] == ["1/2", ">"]


@pytest.mark.asyncio
async def test_paginator_loops_pages_when_enabled() -> None:
    paginator = Paginator(
        pages=[discord.Embed(title="page1"), discord.Embed(title="page2")],
        loop_pages=True,
    )
    view = _PaginatorView(
        paginator.pages,
        paginator.buttons,
        loop_pages=paginator.loop_pages,
        show_disabled=paginator.show_disabled,
    )
    prev_button = next(item for item in view.children if cast(discord.ui.Button, item).label == "<")
    interaction = DummyCallbackInteraction()

    await prev_button.callback(cast(discord.Interaction, interaction))

    assert view.page_index == 1
    assert interaction.response.edit_calls[0][0].title == "page2"

from __future__ import annotations

from typing import Any, cast

import discord
import pytest

from app.common.layout_pages import LayoutPaginator, _LayoutPaginatorView
from app.common.pages import PaginatorButton


class DummyResponse:
    def __init__(self, *, done: bool) -> None:
        self._done = done
        self.send_calls: list[dict[str, Any]] = []
        self.edit_calls: list[dict[str, Any]] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, **kwargs: Any) -> None:
        self.send_calls.append(kwargs)

    async def edit_message(self, **kwargs: Any) -> None:
        self.edit_calls.append(kwargs)


class DummyFollowup:
    def __init__(self, message: object) -> None:
        self.message = message
        self.send_calls: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> object:
        self.send_calls.append(kwargs)
        return self.message


class DummyInteraction:
    def __init__(self, *, done: bool = False) -> None:
        self.response = DummyResponse(done=done)
        self.followup = DummyFollowup(object())
        self.original_message = object()

    async def original_response(self) -> object:
        return self.original_message


def page(content: str) -> discord.ui.Container:
    return discord.ui.Container(discord.ui.TextDisplay(content))


def page_text(view: _LayoutPaginatorView) -> str:
    return next(
        item.content for item in view.walk_children() if isinstance(item, discord.ui.TextDisplay)
    )


@pytest.mark.asyncio
async def test_layout_paginator_responds_with_components_v2_view() -> None:
    paginator = LayoutPaginator(pages=[page("page 1")])
    interaction = DummyInteraction()

    message = await paginator.respond(cast(discord.Interaction, interaction))

    assert message is interaction.original_message
    sent_view = interaction.response.send_calls[0]["view"]
    assert isinstance(sent_view, discord.ui.LayoutView)
    assert sent_view.has_components_v2()
    assert "embed" not in interaction.response.send_calls[0]


@pytest.mark.asyncio
async def test_layout_paginator_moves_to_next_page() -> None:
    view = _LayoutPaginatorView(
        [page("page 1"), page("page 2")],
        [
            PaginatorButton("page_indicator"),
            PaginatorButton("next", label=">"),
        ],
        show_disabled=False,
    )
    next_button = next(
        item
        for item in view.walk_children()
        if isinstance(item, discord.ui.Button) and item.label == ">"
    )
    interaction = DummyInteraction()

    await next_button.callback(cast(discord.Interaction, interaction))

    assert view.page_index == 1
    assert page_text(view) == "page 2"
    assert interaction.response.edit_calls == [{"view": view}]

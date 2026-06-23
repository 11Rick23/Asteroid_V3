from __future__ import annotations

from typing import Any, cast

import discord
import pytest

from app.common.layout_pages import LayoutPaginator, _LayoutPaginatorView, _PageJumpModal
from app.common.pages import PaginatorButton


class DummyResponse:
    def __init__(self, *, done: bool) -> None:
        self._done = done
        self.send_calls: list[dict[str, Any]] = []
        self.edit_calls: list[dict[str, Any]] = []
        self.modal_calls: list[discord.ui.Modal] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, **kwargs: Any) -> None:
        self.send_calls.append(kwargs)

    async def edit_message(self, **kwargs: Any) -> None:
        self.edit_calls.append(kwargs)

    async def send_modal(self, modal: discord.ui.Modal) -> None:
        self.modal_calls.append(modal)


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
    return next(item.content for item in view.walk_children() if isinstance(item, discord.ui.TextDisplay))


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
        item for item in view.walk_children() if isinstance(item, discord.ui.Button) and item.label == ">"
    )
    interaction = DummyInteraction()

    await next_button.callback(cast(discord.Interaction, interaction))

    assert view.page_index == 1
    assert page_text(view) == "page 2"
    assert interaction.response.edit_calls == [{"view": view}]


@pytest.mark.asyncio
async def test_layout_paginator_always_shows_navigation_buttons_and_disables_edges() -> None:
    view = _LayoutPaginatorView(
        [page("page 1"), page("page 2")],
        [
            PaginatorButton("prev", label="<"),
            PaginatorButton("page_indicator"),
            PaginatorButton("next", label=">"),
        ],
        show_disabled=True,
    )

    buttons = [item for item in view.walk_children() if isinstance(item, discord.ui.Button)]

    assert [button.label for button in buttons] == ["<", "1/2", ">"]
    assert [button.disabled for button in buttons] == [True, False, False]

    interaction = DummyInteraction()
    await buttons[2].callback(cast(discord.Interaction, interaction))
    buttons = [item for item in view.walk_children() if isinstance(item, discord.ui.Button)]

    assert [button.label for button in buttons] == ["<", "2/2", ">"]
    assert [button.disabled for button in buttons] == [False, False, True]


@pytest.mark.asyncio
async def test_layout_paginator_page_indicator_opens_jump_modal() -> None:
    view = _LayoutPaginatorView(
        [page("page 1"), page("page 2")],
        [PaginatorButton("page_indicator")],
    )
    indicator = next(
        item for item in view.walk_children() if isinstance(item, discord.ui.Button) and item.label == "1/2"
    )
    interaction = DummyInteraction()

    await indicator.callback(cast(discord.Interaction, interaction))

    assert len(interaction.response.modal_calls) == 1
    assert isinstance(interaction.response.modal_calls[0], _PageJumpModal)


@pytest.mark.asyncio
async def test_layout_paginator_jump_modal_moves_to_requested_page() -> None:
    view = _LayoutPaginatorView(
        [page("page 1"), page("page 2"), page("page 3")],
        [PaginatorButton("page_indicator")],
    )
    modal = _PageJumpModal(view)
    cast(Any, modal.page_number)._value = "3"
    interaction = DummyInteraction()

    await modal.on_submit(cast(discord.Interaction, interaction))

    assert view.page_index == 2
    assert page_text(view) == "page 3"
    assert interaction.response.edit_calls == [{"view": view}]


@pytest.mark.asyncio
async def test_layout_paginator_jump_modal_rejects_out_of_range_page() -> None:
    view = _LayoutPaginatorView(
        [page("page 1"), page("page 2")],
        [PaginatorButton("page_indicator")],
    )
    modal = _PageJumpModal(view)
    cast(Any, modal.page_number)._value = "3"
    interaction = DummyInteraction()

    await modal.on_submit(cast(discord.Interaction, interaction))

    assert view.page_index == 0
    assert interaction.response.send_calls == [
        {
            "content": "1〜2のページ番号を入力してください。",
            "ephemeral": True,
        }
    ]

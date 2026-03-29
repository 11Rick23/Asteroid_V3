from __future__ import annotations

from collections.abc import Sequence

import discord


class PaginatorButton:
    def __init__(
        self,
        kind: str,
        *,
        label: str | None = None,
        style: discord.ButtonStyle = discord.ButtonStyle.gray,
        loop_label: str | None = None,
        disabled: bool = False,
    ):
        self.kind = kind
        self.label = label
        self.style = style
        self.loop_label = loop_label
        self.disabled = disabled


class _PaginatorView(discord.ui.View):
    def __init__(self, pages: Sequence[discord.Embed], buttons: list[PaginatorButton], timeout: float | None = 300):
        super().__init__(timeout=timeout)
        self.pages = list(pages)
        self.page_index = 0
        self.buttons = buttons
        self.message: discord.Message | None = None
        self._build()

    def _build(self) -> None:
        self.clear_items()
        for button in self.buttons:
            if button.kind == "page_indicator":
                control = discord.ui.Button(label=self._indicator_label(), style=button.style, disabled=True)
                self.add_item(control)
                continue

            label = button.label or button.kind
            control = discord.ui.Button(label=label, style=button.style, disabled=button.disabled)

            async def callback(interaction: discord.Interaction, kind: str = button.kind) -> None:
                if kind == "prev":
                    self.page_index = max(0, self.page_index - 1)
                elif kind == "next":
                    self.page_index = min(len(self.pages) - 1, self.page_index + 1)
                self._build()
                await interaction.response.edit_message(embed=self.pages[self.page_index], view=self)

            control.callback = callback
            self.add_item(control)

    def _indicator_label(self) -> str:
        return f"{self.page_index + 1}/{len(self.pages)}"


class Paginator:
    def __init__(
        self,
        *,
        pages: Sequence[discord.Embed],
        use_default_buttons: bool = True,
        loop_pages: bool = False,
        show_disabled: bool = True,
    ):
        del loop_pages, show_disabled
        self.pages = list(pages)
        self.buttons: list[PaginatorButton] = []
        if use_default_buttons:
            self.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
            self.add_button(PaginatorButton("page_indicator"))
            self.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))

    def add_button(self, button: PaginatorButton) -> None:
        self.buttons.append(button)

    async def respond(self, interaction: discord.Interaction) -> discord.Message:
        view = _PaginatorView(self.pages, self.buttons or [PaginatorButton("page_indicator")])
        if interaction.response.is_done():
            await interaction.followup.send(embed=self.pages[0], view=view)
        else:
            await interaction.response.send_message(embed=self.pages[0], view=view)
        message = await interaction.original_response()
        view.message = message
        return message

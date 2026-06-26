from __future__ import annotations

from collections.abc import Sequence

import discord

from app.common.guild_scope import GuildScopedLayoutView, GuildScopedModal
from app.common.pages import PaginatorButton


class _PageJumpModal(GuildScopedModal, title="ページ移動"):
    def __init__(self, paginator_view: _LayoutPaginatorView) -> None:
        super().__init__()
        self.paginator_view = paginator_view
        self.page_number = discord.ui.TextInput(
            label="ページ番号",
            placeholder=f"1〜{len(paginator_view.pages)}",
            min_length=1,
            max_length=len(str(len(paginator_view.pages))),
        )
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.page_number.value.strip()
        if not value.isdecimal():
            await interaction.response.send_message(
                content="ページ番号を数字で入力してください。",
                ephemeral=True,
            )
            return

        page_number = int(value)
        if not 1 <= page_number <= len(self.paginator_view.pages):
            await interaction.response.send_message(
                content=f"1〜{len(self.paginator_view.pages)}のページ番号を入力してください。",
                ephemeral=True,
            )
            return

        self.paginator_view.page_index = page_number - 1
        self.paginator_view._build()
        await interaction.response.edit_message(view=self.paginator_view)


class _LayoutPaginatorView(GuildScopedLayoutView):
    def __init__(
        self,
        pages: Sequence[discord.ui.Container],
        buttons: list[PaginatorButton],
        *,
        loop_pages: bool = False,
        show_disabled: bool = True,
        timeout: float | None = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.pages = list(pages)
        self.page_index = 0
        self.buttons = buttons
        self.loop_pages = loop_pages
        self.show_disabled = show_disabled
        self.message: discord.Message | None = None
        self._build()

    def _build(self) -> None:
        self.clear_items()
        self.add_item(self.pages[self.page_index])

        controls: list[discord.ui.Button[_LayoutPaginatorView]] = []
        for button in self.buttons:
            if button.kind == "page_indicator":
                control = discord.ui.Button[_LayoutPaginatorView](
                    label=self._indicator_label(),
                    style=button.style,
                    disabled=button.disabled,
                )
                if not button.disabled:

                    async def indicator_callback(interaction: discord.Interaction) -> None:
                        await interaction.response.send_modal(_PageJumpModal(self))

                    control.callback = indicator_callback
                controls.append(control)
                continue

            label = button.label or button.kind
            disabled = button.disabled
            if button.kind == "prev":
                at_edge = self.page_index == 0
                if at_edge and not self.loop_pages:
                    disabled = True
                    if not self.show_disabled:
                        continue
                elif at_edge:
                    label = button.loop_label or label
            elif button.kind == "next":
                at_edge = self.page_index == len(self.pages) - 1
                if at_edge and not self.loop_pages:
                    disabled = True
                    if not self.show_disabled:
                        continue
                elif at_edge:
                    label = button.loop_label or label

            control = discord.ui.Button[_LayoutPaginatorView](
                label=label,
                style=button.style,
                disabled=disabled,
            )

            async def callback(interaction: discord.Interaction, kind: str = button.kind) -> None:
                if kind == "prev":
                    if self.page_index == 0:
                        if self.loop_pages:
                            self.page_index = len(self.pages) - 1
                    else:
                        self.page_index -= 1
                elif kind == "next":
                    if self.page_index == len(self.pages) - 1:
                        if self.loop_pages:
                            self.page_index = 0
                    else:
                        self.page_index += 1
                self._build()
                await interaction.response.edit_message(view=self)

            control.callback = callback
            controls.append(control)

        if controls:
            self.add_item(discord.ui.ActionRow(*controls))

    def _indicator_label(self) -> str:
        return f"{self.page_index + 1}/{len(self.pages)}"


class LayoutPaginator:
    def __init__(
        self,
        *,
        pages: Sequence[discord.ui.Container],
        use_default_buttons: bool = True,
        loop_pages: bool = False,
        show_disabled: bool = True,
    ) -> None:
        if not pages:
            raise ValueError("pages must not be empty")
        self.pages = list(pages)
        self.loop_pages = loop_pages
        self.show_disabled = show_disabled
        self.buttons: list[PaginatorButton] = []
        if use_default_buttons:
            self.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
            self.add_button(PaginatorButton("page_indicator"))
            self.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))

    def add_button(self, button: PaginatorButton) -> None:
        self.buttons.append(button)

    async def respond(self, interaction: discord.Interaction) -> discord.Message:
        view = _LayoutPaginatorView(
            self.pages,
            self.buttons or [PaginatorButton("page_indicator")],
            loop_pages=self.loop_pages,
            show_disabled=self.show_disabled,
        )
        if interaction.response.is_done():
            message = await interaction.followup.send(view=view, wait=True)
        else:
            await interaction.response.send_message(view=view)
            message = await interaction.original_response()
        view.message = message
        return message

from __future__ import annotations

import discord
from discord import ui

from typing import TYPE_CHECKING, TypeVar, Generic

if TYPE_CHECKING:
    from typing import Any, Self, Optional


T = TypeVar("T")


class SkipToPage(ui.Modal, title="Skip to page"):
    page: ui.TextInput[Self]
    total: int

    @classmethod
    def from_total(cls, total: int) -> Self:
        inst = cls()
        inst.page = ui.TextInput(
            label=f"Please enter a page within the range 1-{total}",
        )
        inst.total = total

        inst.add_item(inst.page)
        return inst

    async def on_submit(self, interaction: discord.Interaction):
        value = self.page.value
        total = self.total

        if not value.isdigit():
            raise ValueError

        value = int(value)
        if not (total >= value > 0):
            raise ValueError

        await interaction.response.defer()

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, ValueError):
            await interaction.response.send_message(
                f"Please enter a number between 1-{self.total}", ephemeral=True
            )
        else:
            return await super().on_error(interaction, error)


class BasePaginator(ui.View, Generic[T]):
    def __init__(
        self,
        data: list[T],
        *,
        count: int = 0,
        page: int = 1,
        limit_to_user: Optional[discord.Object] = None,
        **kwargs: Any,
    ):
        self.data = data
        self.count = count or len(data)
        self.page = page
        self.msg = None
        self.limit_to_user = limit_to_user
        super().__init__(**kwargs)

        self.update_buttons()

    async def send(
        self,
        dest: discord.abc.Messageable,
        *args: Any,
        **kwargs: Any,
    ):
        response = await self.format_page(
            self.data[self.page - 1],
        )

        self.msg = await dest.send(
            *args,
            view=self,
            **kwargs,
            **response,
        )

    async def format_page(self, page: T) -> dict[str, Any]:
        raise NotImplementedError

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.limit_to_user and interaction.user.id != self.limit_to_user.id:
            await interaction.response.send_message(
                "You can't use this paginator, try invoking the command yourself.",
                ephemeral=True,
            )

            return False

        return True

    async def respond_or_edit(
        self,
        interaction: discord.Interaction,
        *args: Any,
        **kwargs: Any,
    ):
        if interaction.response.is_done():
            await interaction.edit_original_response(*args, **kwargs)
        else:
            await interaction.response.edit_message(*args, **kwargs)

    async def _go_to_item(self, interaction: discord.Interaction, page: int):
        if not (0 < page <= len(self.data)):
            await interaction.response.send_message(
                f"Page overflow! you can't move to page `{page}` from page `{self.page}`.",
                ephemeral=True,
            )

            return

        self.page = page
        self.update_buttons()

        response = await self.format_page(
            self.data[self.page - 1],
        )

        await self.respond_or_edit(
            interaction,
            view=self,
            **response,
        )

    def update_buttons(self):
        self._first.disabled = False
        self._prev.disabled = False
        self._next.disabled = False
        self._last.disabled = False

        if self.page <= 1:
            self._first.disabled = True
            self._prev.disabled = True

        if self.page >= self.count:
            self._next.disabled = True
            self._last.disabled = True

        self._page.label = f"{self.page}/{self.count}"

    async def on_timeout(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled") and not isinstance(child, ui.DynamicItem):
                child.disabled = True  # type: ignore

        if self.msg:
            await self.msg.edit(view=self)

    @ui.button(label="<<")
    async def _first(self, interaction: discord.Interaction, _: ui.Button[Self]):
        await self._go_to_item(interaction, 1)

    @ui.button(label="<")
    async def _prev(self, interaction: discord.Interaction, _: ui.Button[Self]):
        await self._go_to_item(interaction, self.page - 1)

    @ui.button(label="\u200b")
    async def _page(self, interaction: discord.Interaction, _: ui.Button[Self]):
        modal = SkipToPage.from_total(self.count)
        await interaction.response.send_modal(modal)
        await modal.wait()

        await self._go_to_item(
            interaction,
            int(modal.page.value),
        )

    @ui.button(label=">")
    async def _next(self, interaction: discord.Interaction, _: ui.Button[Self]):
        await self._go_to_item(interaction, self.page + 1)

    @ui.button(label=">>")
    async def _last(self, interaction: discord.Interaction, _: ui.Button[Self]):
        await self._go_to_item(interaction, self.count)


class ChunkedPaginator(BasePaginator[T]):
    def __init__(
        self,
        count: int,
        *,
        page: int = 1,
        chunk: int = 0,
        per_chunk: int = 15,
        **kwargs: Any,
    ):
        self.data: list[T] = []
        self.count = count
        self.page = page
        self.chunk = chunk
        self.per_chunk = per_chunk

        super().__init__(self.data, count=count, **kwargs)

        self.update_buttons()

    async def send(
        self,
        dest: discord.abc.Messageable,
        *args: Any,
        **kwargs: Any,
    ):
        self.data = await self.fetch_chunk(0)

        response = await self.format_page(
            self.data[(self.page - 1) % self.per_chunk],
        )

        await dest.send(
            *args,
            view=self,
            **response,
            **kwargs,
        )

    async def fetch_chunk(self, chunk: int) -> list[T]:
        raise NotImplementedError

    async def _go_to_item(self, interaction: discord.Interaction, page: int):
        if not (0 < page <= self.count):
            await interaction.response.send_message(
                f"Page overflow! you can't move to page `{page}` from page `{self.page}`.",
                ephemeral=True,
            )

            return

        chunk = (page - 1) // self.per_chunk
        if self.chunk != chunk:
            self.chunk = chunk
            self.data = await self.fetch_chunk(self.chunk)

        self.page = page

        self.update_buttons()

        response = await self.format_page(
            self.data[(self.page - 1) % self.per_chunk],
        )
        await self.respond_or_edit(interaction, view=self, **response)

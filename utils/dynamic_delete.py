from __future__ import annotations

from discord import (
    Interaction,
    ui,
    ButtonStyle,
)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Self

    from re import Match


class DeleteButton(
    ui.DynamicItem[ui.Button[ui.View]],
    template=r"kana:delete_(?P<user_id>\d+)",
):
    def __init__(self, user_id: int):
        super().__init__(
            ui.Button[ui.View](
                emoji="\U0001f5d1",
                style=ButtonStyle.danger,
                custom_id=f"kana:delete_{user_id}",
            ),
        )

        self.user_id = user_id

    @classmethod
    async def from_custom_id(
        cls: type[Self],
        _interaction: Interaction,
        _item: ui.Item[Any],
        match: Match[str],
        /,
    ) -> Self:
        return cls(
            user_id=int(match["user_id"]),
        )

    async def callback(self, interaction: Interaction):
        if self.user_id != interaction.user.id:
            return await interaction.response.send_message(
                "This is not your message to be deleted.",
                ephemeral=True,
            )

        await interaction.delete_original_response()

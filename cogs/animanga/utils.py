from __future__ import annotations

import discord
from discord import ui

import re
from urllib.parse import quote

from utils.constants import BELL, BOOK, CAMERA, NO_BELL
from libs.anilist.types import FetchResult, Relation, SearchType

from typing import TYPE_CHECKING, Optional, Self

if TYPE_CHECKING:
    from . import Animanga
    from utils.subclasses import Bot


class View(ui.View):
    @classmethod
    async def from_result(
        cls,
        interaction: discord.Interaction[Bot],
        result: FetchResult,
    ) -> Optional[Self]:
        view = None
        if result["relations"]:
            view = view or cls(timeout=None)
            view.add_item(RelationSelect(result["relations"]))

        if result["trailer"]:
            view = view or cls(timeout=None)
            view.add_item(
                ui.Button(
                    label="Trailer",
                    url=result["trailer"].strip(),
                    row=2,
                )
            )

        if result["nextAiringEpisode"]:
            view = view or cls(timeout=None)
            view.add_item(
                await ReminderButton.for_user(
                    interaction.client, result["id"], interaction.user.id
                )
            )

        return view


class RelationSelect(
    ui.DynamicItem[ui.Select[View]], template=r"kana:animanga_relations"
):
    def __init__(self, relations: list[Relation]) -> None:
        super().__init__(
            ui.Select[View](
                placeholder="Related",
                custom_id="kana:animanga_relations",
                options=self._to_options(relations),
                row=1,
            ),
        )

    def _to_options(self, relations: list[Relation]) -> list[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=relation["title"],
                description=relation["relation_type"].replace("_", " ").title(),
                emoji=BOOK if relation["type"] == "MANGA" else CAMERA,
                value=f"{relation['type']}_{relation['id']}",
                default=False,
            )
            for relation in relations
        ][:25]

    async def _query_anilist(
        self,
        interaction: discord.Interaction["Bot"],
        search_id: str,
        search_type: str,
        *,
        attempt: int = 0,
    ) -> Optional[FetchResult]:
        result = await interaction.client.anilist.fetch(
            f"x (ID: {search_id})",  # bit jank but who is gonna stop me
            search_type=SearchType.ANIME
            if search_type == "ANIME"
            else SearchType.MANGA,
        )

        if not result and attempt < 3:
            return await self._query_anilist(
                interaction, search_id, search_type, attempt=attempt
            )

        return result

    @classmethod
    async def from_custom_id(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        _interaction: discord.Interaction[Bot],
        _item: ui.Select[View],
        _match: re.Match[str],
    ) -> Self:
        return cls([])

    async def callback(self, interaction: discord.Interaction["Bot"]):  # type: ignore
        await interaction.response.defer(ephemeral=True)
        search_type, search_id = self.item.values[0].split("_")

        result = await self._query_anilist(interaction, search_id, search_type)

        if not result:
            return await interaction.edit_original_response(view=self.view)

        view = await View.from_result(interaction, result)

        await interaction.followup.send(
            embed=AnimangaEmbed.from_result(result),
            ephemeral=True,
            view=view,  # pyright: ignore[reportArgumentType]
        )


class ReminderButton(
    ui.DynamicItem[ui.Button[ui.View]],
    template=r"kana:r_(?P<anime_id>\d+)_(?P<user_id>\d+)",
):
    def __init__(
        self,
        is_active: bool,
        anime_id: int,
        user_id: int,
    ):
        super().__init__(
            ui.Button[ui.View](
                emoji=BELL if is_active else NO_BELL,
                style=discord.ButtonStyle.green
                if is_active
                else discord.ButtonStyle.gray,
                custom_id=f"kana:r_{anime_id}_{user_id}",
                row=2,
            ),
        )

        self.anime_id = anime_id
        self.user_id = user_id

    @classmethod
    async def for_user(
        cls,
        bot: Bot,
        anime_id: int,
        user_id: int,
    ) -> Self:
        is_active = await bot.pool.fetchval(
            """
            SELECT TRUE FROM anime_reminders
                WHERE anilist_id = $1
                  AND user_id = $2
            """,
            anime_id,
            user_id,
        )

        return cls(is_active, anime_id, user_id)

    async def toggle_reminder(
        self,
        bot: Bot,
        anime_id: int,
        user_id: int,
    ) -> bool:
        reminder: Optional[Animanga] = bot.get_cog("Animanga")  # pyright: ignore[reportAssignmentType]
        if not reminder:
            raise ValueError("Animanga cog not loaded")

        toggle = await reminder.toggle_reminder_for(user_id, anime_id)
        return toggle

    @classmethod
    async def from_custom_id(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        interaction: discord.Interaction[Bot],
        _: ui.Button[ui.View],
        match: re.Match[str],
    ) -> Self:
        anime_id, user_id = int(match["anime_id"]), int(match["user_id"])
        is_active = await interaction.client.pool.fetchval(
            """
            SELECT TRUE FROM anime_reminders
                WHERE anilist_id = $1
                  AND user_id = $2
            """,
            anime_id,
            user_id,
        )

        return cls(is_active, anime_id, user_id)

    def _re_add_button(self):
        if not self.view:
            return

        self.view.remove_item(self)
        self.view.add_item(self)

    async def callback(self, interaction: discord.Interaction[Bot]):  # pyright: ignore[reportIncompatibleMethodOverride]
        assert self.view

        is_toggled = await self.toggle_reminder(
            interaction.client, self.anime_id, self.user_id
        )

        if self.user_id == interaction.user.id:
            self.item.style = (
                discord.ButtonStyle.green if is_toggled else discord.ButtonStyle.gray
            )
            self.item.emoji = BELL if is_toggled else NO_BELL
            self._re_add_button()

            return await interaction.response.edit_message(view=self.view)

        await interaction.response.send_message(
            "Reminder set! I'll remind you when a future episode premieres."
            if is_toggled
            else "Reminder removed.",
            ephemeral=True,
        )


class AnimangaEmbed(discord.Embed):
    @classmethod
    def from_result(cls, data: FetchResult) -> Self:
        embed = cls(
            title=data["title"],
            description=data["description"],
            color=discord.Color.from_str(data["color"]) if data["color"] else 0xE6E6E6,
            url=data["siteUrl"],
        )

        embed.set_thumbnail(url=data["coverImage"])
        embed.set_image(url=data["bannerImage"])

        embed.add_field(
            name="Genres",
            value=", ".join(
                f"[{genre}](https://anilist.co/search/{data['type'].name.lower()}?genres={quote(genre)})"
                for genre in data["genres"]
            ),
        )
        embed.add_field(
            name="Score",
            value=f"{data['averageScore']}/100" if data["averageScore"] else "NaN",
        )
        embed.add_field(name="Status", value=data["status"])

        if data["episodes"]:
            embed.add_field(name="Episodes", value=data["episodes"])

        if data["studios"]:
            embed.add_field(
                name="Studio",
                value=data["studios"][0][
                    "formatted"
                ],  # always going to be the main studio
            )

        if data["chapters"]:
            embed.add_field(name="Chapters", value=data["chapters"])

        return embed


def is_nsfw(interaction: discord.Interaction, result: FetchResult) -> bool:
    assert interaction.channel

    if result["isAdult"] and not (
        isinstance(
            interaction.channel,
            discord.DMChannel | discord.PartialMessageable | discord.GroupChannel,
        )
        or interaction.channel.is_nsfw()
    ):
        return True

    return False

from __future__ import annotations

import discord
from discord import app_commands

from .. import BaseCog
from .utils import View, AnimangaEmbed, ReminderButton, RelationSelect, is_nsfw

from utils.constants import NSFW_ERROR_MSG

from libs.anilist import AniList
from libs.anilist.types import SearchType

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.subclasses import Bot


class AnimangaFrontend(BaseCog):
    def __init__(self, bot: "Bot"):
        super().__init__(bot)
        self.anilist = self.bot.anilist
        self.bot.add_dynamic_items(ReminderButton, RelationSelect)

    anime = app_commands.Group(
        name="anime",
        description="...",
    )

    @anime.command(name="search")
    @app_commands.autocomplete(query=AniList.search_auto_complete)
    async def anime_search(self, interaction: discord.Interaction[Bot], query: str):
        """
        Search for an Anime.

        Parameters
        -----------
        query: str
            The Anime to search for.
        """
        await interaction.response.defer()

        result = await self.anilist.fetch(query, search_type=SearchType.ANIME)
        if not result:
            return await interaction.edit_original_response(content="No anime found.")

        if is_nsfw(interaction, result):
            return await interaction.edit_original_response(
                content=NSFW_ERROR_MSG % "anime"
            )

        embed = AnimangaEmbed.from_result(result)
        view = await View.from_result(interaction, result)

        await interaction.edit_original_response(
            embed=embed,
            view=view,  # pyright: ignore[reportArgumentType]
        )

    manga = app_commands.Group(
        name="manga",
        description="...",
    )

    @manga.command(name="search")
    @app_commands.autocomplete(query=AniList.search_auto_complete)
    async def manga_search(self, interaction: discord.Interaction[Bot], query: str):
        """
        Search for a Manga.

        Parameters
        -----------
        query: str
            The Manga to search for.
        """
        await interaction.response.defer()

        result = await self.anilist.fetch(query, search_type=SearchType.MANGA)
        if not result:
            return await interaction.edit_original_response(content="No Manga found.")

        if is_nsfw(interaction, result):
            return await interaction.edit_original_response(
                content=NSFW_ERROR_MSG % "manga"
            )

        view = await View.from_result(interaction, result)

        embed = AnimangaEmbed.from_result(result)
        await interaction.edit_original_response(
            embed=embed,
            view=view,  # pyright: ignore[reportArgumentType]
        )

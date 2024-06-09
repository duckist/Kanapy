from __future__ import annotations

from discord import app_commands
from discord.ext import commands

from .. import BaseCog
from .utils import (
    View,
    AnimangaEmbed,
    ReminderButton,
    RelationSelect,
    is_nsfw,
)

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

    async def _search(
        self,
        ctx: commands.Context[Bot],
        query: str,
        *,
        search_type: SearchType,
    ):
        media = await self.anilist.fetch(query, search_type=search_type)
        if not media:
            return await ctx.send(content=f"No {search_type.name.lower()} found.")

        if is_nsfw(ctx, media):
            return await ctx.send(content=NSFW_ERROR_MSG % search_type.name.lower())

        embed = AnimangaEmbed.from_media(media)
        view = await View.from_media(
            media,
            ctx.bot,
            ctx.author.id,
        )

        await ctx.send(
            embed=embed,
            view=view,
        )

    @commands.hybrid_group(description="...")
    async def anime(
        self,
        ctx: commands.Context[Bot],
        *,
        query: str,
    ):
        """
        Base command for Anime related things. On its own it will search for animes,
        but you can do other stuff from its sub-commands.

        Parameters
        -----------
        query: str
            The Anime to search for.
        """

        await ctx.invoke(self.anime_search, query=query)

    @anime.command(name="search", invoke_without_command=True)
    @app_commands.autocomplete(query=AniList.search_auto_complete)
    async def anime_search(
        self,
        ctx: commands.Context[Bot],
        *,
        query: str,
    ):
        """
        Search for an Anime.

        Parameters
        -----------
        query: str
            The Anime to search for.
        """

        return await self._search(
            ctx,
            query,
            search_type=SearchType.ANIME,
        )

    @commands.hybrid_group(description="...")
    async def manga(
        self,
        ctx: commands.Context[Bot],
        *,
        query: str,
    ):
        """
        Base command for Manga related things. On its own it will search for mangas,
        but you can do other stuff from its sub-commands.

        Parameters
        -----------
        query: str
            The Manga to search for.
        """

        await ctx.invoke(self.manga_search, query=query)

    @manga.command(name="search")
    @app_commands.autocomplete(query=AniList.search_auto_complete)
    async def manga_search(self, ctx: commands.Context[Bot], query: str):
        """
        Search for a Manga.

        Parameters
        -----------
        query: str
            The Manga to search for.
        """

        return await self._search(
            ctx,
            query,
            search_type=SearchType.MANGA,
        )

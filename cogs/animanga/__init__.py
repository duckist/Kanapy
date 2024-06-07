from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .. import BaseCog
from .utils import (
    MediaView,
    MediaEmbed,
    ReminderButton,
    RelationSelect,
    AniListUserConverter,
    LoginView,
    is_nsfw,
)

from utils.constants import NSFW_ERROR_MSG

from libs.anilist import AniList
from libs.anilist.types import SearchType

from .reminders import Reminders

from typing import TYPE_CHECKING, Annotated, Optional

if TYPE_CHECKING:
    from utils.subclasses import Bot


class Animanga(Reminders, BaseCog):
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

        embed = MediaEmbed.from_data(media)
        view = await MediaView.from_data(
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

        return self._search(
            ctx,
            query,
            search_type=SearchType.ANIME,
        )

    @commands.group(name="anilist", invoke_without_command=True)
    async def _anilist(
        self,
        ctx: commands.Context[Bot],
        args: Annotated[Optional[int], AniListUserConverter] = None,
    ):
        """
        Shows the current logged in profile for your linked AniList account.
        """

        await ctx.invoke(self._anilist_user, args)

    @_anilist.command(name="login")
    async def _anilist_login(self, ctx: commands.Context[Bot]):
        """
        Login to your AniList account.
        """

        embed = discord.Embed(
            title="AniList Login",
            description="Head over to the link below to obtain your AniList access token. Submit the token by pressing the button below.",
        )

        await ctx.send(embed=embed, view=LoginView(ctx.bot))

    @_anilist.command(name="logout")
    async def _anilist_logout(self, ctx: commands.Context[Bot]):
        """
        Logs out of your AniList account.
        """

        val = await ctx.bot.pool.execute(
            "DELETE FROM anilist_tokens WHERE user_id = $1",
            ctx.author.id,
        )

        if val.endswith("0"):
            return await ctx.send("You're not logged in to be logged out.")

        await ctx.send("Logged out.")

    @_anilist.command(name="user")
    async def _anilist_user(
        self,
        ctx: commands.Context[Bot],
        user: Annotated[Optional[int], AniListUserConverter] = None,
    ):
        if user is None:
            user = await AniListUserConverter().convert(ctx, str(ctx.author.id))

        await ctx.send(f"{user}")

    @_anilist.command(name="list")
    async def _anilist_list(
        self,
        ctx: commands.Context[Bot],
        user: Annotated[Optional[int], AniListUserConverter] = None,
    ): ...


async def setup(bot: "Bot"):
    await bot.add_cog(Animanga(bot))

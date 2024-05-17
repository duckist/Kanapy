from __future__ import annotations

import discord
from discord import ui
from discord.ext import commands

from typing import Any, Optional, TYPE_CHECKING

from .. import BaseCog
from libs.spotify import SpotifyClient, SearchType

from utils import cutoff

if TYPE_CHECKING:
    from utils.subclasses import Bot, Context


class Dropdown(ui.Select["ResultView"]):
    def __init__(self, items: list[dict[str, str]], *args: Any, **kwargs: Any):
        self.items = [{k: cutoff(v, 100) for k, v in item.items()} for item in items]

        options = [
            discord.SelectOption(**item, default=True if _iter == 0 else False)
            for _iter, item in enumerate(self.items)
        ]

        kwargs["options"] = options
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        self.options = [
            discord.SelectOption(
                **item,
                default=True if self.values[0] == item["value"] else False,
            )
            for item in self.items
        ]

        await interaction.response.edit_message(content=self.values[0], view=self.view)


class ResultView(ui.View):
    def __init__(
        self, items: list[dict[str, str]], author_id: int, *args: Any, **kwargs: Any
    ):
        super().__init__(*args, **kwargs)
        self.author_id = author_id
        self.original_message: Optional[discord.Message] = None

        self.add_item(Dropdown(items))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "this isn't your command dummy", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True  # type: ignore

        if self.original_message:  # pesky pesky linter
            await self.original_message.edit(view=self)


class SpotifySearch(BaseCog):
    def __init__(self, bot: "Bot") -> None:
        super().__init__(bot)
        self.SPOTIFY_EMOJI = self.CONFIG["Emojis"]["SPOTIFY"]
        self.spotify = SpotifyClient(self.bot.session)

    @commands.group(name="spotify", aliases=["sp"], invoke_without_command=True)
    @commands.cooldown(3, 1, commands.BucketType.user)
    async def _spotify(self, ctx: Context, *, query: str):
        """
        Base command for Spotify related things. On its own it will search for songs,
        but you can search for other stuff from its sub-commands.

        Parameters
        ----------
        query: str
            The song search query.
        """

        await ctx.invoke(self._spotify_search, query=query)

    @_spotify.command(name="search", aliases=["s", "track", "tc"])
    @commands.cooldown(3, 1, commands.BucketType.user)
    async def _spotify_search(self, ctx: Context, *, query: str):
        """
        Searches songs on Spotify.

        Parameters
        ----------
        query: str
            The song search query.
        """

        resp = await self.spotify.search(query, search_type=SearchType.tracksV2)

        if not resp:
            return await ctx.send("No results.")

        items: list[dict[str, str]] = []
        for item in resp:
            items.append(
                {
                    "label": item["track_name"],
                    "value": item["track_url"],
                    "description": " · ".join(
                        [artist["name"] for artist in item["artists"]]
                    )[:100],
                    "emoji": self.SPOTIFY_EMOJI,
                }
            )

        view = ResultView(items, ctx.author.id)
        view.original_message = await ctx.send(resp[0]["track_url"], view=view)

    @_spotify.command(name="artist", aliases=["art", "a"])
    @commands.cooldown(3, 1, commands.BucketType.user)
    async def _spotify_artist(self, ctx: Context, *, query: str):
        """
        Searches artists on Spotify.

        Parameters
        ----------
        query: str
            The artist search query.
        """

        resp = await self.spotify.search(query, search_type=SearchType.artists)

        if not resp:
            return await ctx.send("No results.")

        items: list[dict[str, str]] = []
        for item in resp:
            items.append(
                {
                    "label": item["name"],
                    "value": item["url"],
                    "emoji": self.SPOTIFY_EMOJI,
                }
            )

        view = ResultView(items, ctx.author.id)
        view.original_message = await ctx.send(resp[0]["url"], view=view)

    @_spotify.command(name="playlist", aliases=["playlists", "pl"])
    @commands.cooldown(3, 1, commands.BucketType.user)
    async def _spotify_playlist(self, ctx: Context, *, query: str):
        """
        Searches playlists on Spotify.

        Parameters
        ----------
        query: str
            The playlist search query.
        """

        resp = await self.spotify.search(query, search_type=SearchType.playlists)

        if not resp:
            return await ctx.send("No results.")

        items: list[dict[str, str]] = []
        for item in resp:
            items.append(
                {
                    "label": item["name"],
                    "value": item["url"],
                    "emoji": self.SPOTIFY_EMOJI,
                }
            )

        view = ResultView(items, ctx.author.id)
        view.original_message = await ctx.send(resp[0]["url"], view=view)

    @_spotify.command(name="album", aliases=["albums", "al"])
    @commands.cooldown(3, 1, commands.BucketType.user)
    async def _spotify_albums(self, ctx: Context, *, query: str):
        """
        Searches albums on Spotify.

        Parameters
        ----------
        query: str
            The album search query.
        """

        resp = await self.spotify.search(query, search_type=SearchType.albums)

        if not resp:
            return await ctx.send("No results.")

        items: list[dict[str, str]] = []
        for item in resp:
            items.append(
                {
                    "label": item["name"],
                    "value": item["url"],
                    "emoji": self.SPOTIFY_EMOJI,
                }
            )

        view = ResultView(items, ctx.author.id)
        view.original_message = await ctx.send(resp[0]["url"], view=view)

    @_spotify.command(name="podcast", aliases=["podcasts", "p", "pd", "pod"])
    @commands.cooldown(3, 1, commands.BucketType.user)
    async def _spotify_podcast(self, ctx: Context, *, query: str):
        """
        Searches podcasts on Spotify.

        Parameters
        ----------
        query: str
            The podcast search query.
        """

        resp = await self.spotify.search(query, search_type=SearchType.podcasts)

        if not resp:
            return await ctx.send("No results.")

        items: list[dict[str, str]] = []
        for item in resp:
            items.append(
                {
                    "label": item["name"],
                    "value": item["url"],
                    "emoji": self.SPOTIFY_EMOJI,
                }
            )

        view = ResultView(items, ctx.author.id)
        view.original_message = await ctx.send(resp[0]["url"], view=view)


class Search(SpotifySearch): ...


async def setup(bot: "Bot"):
    await bot.add_cog(Search(bot))

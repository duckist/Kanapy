from __future__ import annotations

import discord
from discord.ext import commands

from utils.subclasses import Bot as Bot

from . import BaseCog
from utils.paginator import BasePaginator

from libs.doujins import DoujinClient
from libs.doujins.types import Gallery

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Any

    from . import Bot, Context


class DoujinPaginator(BasePaginator[str]):
    def __init__(
        self,
        gallery: Gallery,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(data=gallery.pages, *args, **kwargs)
        self.gallery = gallery
        self.BASE_EMBED = (
            discord.Embed(
                title=self.gallery.title["pretty"],
                url=gallery.url,
                timestamp=self.gallery.uploaded_at,
            )
            .set_thumbnail(url=self.gallery.thumbnail)
            .set_footer(text=f"\U00002764 {self.gallery.favourites}")
        )

        for k, v in self.gallery.tags.items():
            values = [
                *map(
                    lambda tag: f"[`{tag.name}`]({tag.url})",
                    v,
                )
            ]

            if values:
                self.BASE_EMBED.add_field(
                    name=k.title(),
                    value=",".join(values[:5]),
                    inline=True,
                )

    async def format_page(self, page: str) -> dict[str, Any]:
        return {
            "embed": self.BASE_EMBED.set_image(url=page),
        }


class Doujins(BaseCog):
    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self.client = DoujinClient()

    @commands.command()
    @commands.is_nsfw()
    async def doujin(
        self,
        ctx: Context,
        doujin: int,
    ):
        """
        Read a doujin from its ID.
        """

        q = await self.client.fetch_doujin(doujin)
        if not q:
            return await ctx.send("Could not find a doujin with that id.")

        await DoujinPaginator(q).send(ctx)


async def setup(bot: "Bot"):
    await bot.add_cog(Doujins(bot))

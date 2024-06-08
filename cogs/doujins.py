from __future__ import annotations

import discord
from discord.ext import commands

from utils.paginator import BasePaginator
from utils.dynamic_delete import DeleteButton

from libs.doujins import DoujinClient
from libs.doujins.types import Gallery, Tag

from . import BaseCog

from typing import TYPE_CHECKING

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

        if self.limit_to_user:
            self.add_item(DeleteButton(self.limit_to_user.id))

        self.BASE_EMBED = (
            discord.Embed(
                title=self.gallery.title["pretty"],
                url=self.gallery.url,
                timestamp=self.gallery.uploaded_at,
            )
            .set_thumbnail(url=self.gallery.thumbnail)
            .set_footer(text=f"\U00002764 {self.gallery.favourites}")
        )

        tags = self.gallery.tags.pop("tag")

        for k, v in self.gallery.tags.items():
            self._add_embed_field(k, v)

        self._add_embed_field("tags", tags, inline=False)

    def _add_embed_field(
        self,
        name: str,
        tags: list[Tag],
        *,
        inline: bool = True,
    ):
        values = [
            *map(
                lambda tag: f"[`{tag.name}`]({tag.url})",
                tags,
            )
        ]

        if values:
            self.BASE_EMBED.add_field(
                name=name.title(),
                value=", ".join(values[:5]),
                inline=inline,
            )

    async def format_page(self, page: str) -> dict[str, Any]:
        return {
            "embed": self.BASE_EMBED.set_image(url=page),
        }


class Doujins(BaseCog):
    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        self.client = await DoujinClient.new(self.CONFIG["FLARESOLVER_URL"])

    async def cog_unload(self):
        await super().cog_unload()
        await self.client.session.close()

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.is_nsfw()
    async def doujin(
        self,
        ctx: Context,
        doujin: int,
    ):
        """
        Read a doujin from its ID.
        """

        async with ctx.typing():
            q = await self.client.fetch_doujin(doujin)
            if not q:
                return await ctx.send("Could not find a doujin with that id.")

            await DoujinPaginator(q, limit_to_user=ctx.author).send(ctx)


async def setup(bot: "Bot"):
    await bot.add_cog(Doujins(bot))

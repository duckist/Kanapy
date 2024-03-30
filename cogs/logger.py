from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict

import discord
from discord import ui
from discord.ext import commands

import asyncio
import math

from datetime import datetime
from io import BytesIO

from . import BaseCog, logger

if TYPE_CHECKING:
    from utils.subclasses import Bot
    from typing import Any
    from typing_extensions import Self


GUILD_FILESIZE_LIMIT = 25 * 1024 * 1024  # as that's what basic guilds get.


class NoAvatarData(Exception): ...


class AvatarData(TypedDict):
    user: discord.User
    avatars: list[tuple[str, datetime]]
    count: int  # total count of avatars
    idx: int  # current avatar of offset n
    offset: int  # current offset


class SkipToPage(ui.Modal, title="Skip to page"):
    page: ui.TextInput[Self]
    total: int

    @classmethod
    def with_data(cls, total: int) -> Self:
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


class AvatarPaginator(ui.View):
    PER_CHUNK = 15
    bot: "Bot"
    data: AvatarData
    message: discord.Message

    @classmethod
    async def populate_data(
        cls,
        bot: Bot,
        message: discord.Message,
        user: discord.User,
        *args: Any,
        **kwargs: Any,
    ) -> Self:
        inst = cls(*args, **kwargs)
        inst.bot = bot
        inst.message = message

        count = await inst.get_count(user.id)

        if count <= 0:
            raise NoAvatarData

        inst.data = {
            "avatars": [],
            "user": user,
            "count": count,
            "idx": 0,
            "offset": 0,
        }
        inst.data["avatars"] = await inst.fetch_chunk(0)
        inst.update_buttons()

        return inst

    async def fetch_chunk(self, offset: int) -> list[tuple[str, datetime]]:
        records = await self.bot.pool.fetch(
            """
            SELECT avatar_url, changed_at
                FROM avatar_history
            WHERE
                user_id = $1
                AND changed_at < $2
            ORDER BY
                changed_at DESC
            LIMIT $3
                OFFSET $4;
        """,
            self.data["user"].id,
            self.message.created_at,
            self.PER_CHUNK,
            offset,
        )

        return [(record["avatar_url"], record["changed_at"]) for record in records]

    async def get_count(self, user_id: int):
        count = await self.bot.pool.fetchval(
            """
            SELECT
                COUNT(*)
            FROM avatar_history
            WHERE
                user_id = $1
                AND changed_at < $2;
        """,
            user_id,
            self.message.created_at,
        )

        return count

    async def _goto(self, page: int, itx: discord.Interaction | None = None):
        total = self.data["count"]
        if (page + 1) > total or page < 0:
            if itx:
                await itx.response.send_message(
                    f"Page overflow! you can't move to page `{page + 1}` from page `{self.data['idx'] + 1}`.",
                    ephemeral=True,
                )

            return

        self.data["idx"] = page
        page += 1

        curr_offset = self.data["offset"]
        if not ((curr_offset + self.PER_CHUNK) > page > curr_offset):
            offset = abs(
                (math.ceil(page / self.PER_CHUNK) - 1) * self.PER_CHUNK,
            )
            self.data["avatars"] = await self.fetch_chunk(offset)
            self.data["offset"] = offset

        self.update_buttons()

        message = {
            "embed": self.create_embed(),
            "view": self,
        }

        if itx:
            if itx.response.is_done() and itx.message:
                await itx.message.edit(**message)  # type: ignore
            else:
                await itx.response.edit_message(**message)  # type: ignore

    def create_embed(self) -> discord.Embed:
        data = self.data["avatars"][self.data["idx"] % self.PER_CHUNK]

        return (
            discord.Embed(
                title=f"{self.data['user'].name}'s Avatar History",
                description=f"Changed At: {discord.utils.format_dt(data[1])} ({discord.utils.format_dt(data[1], 'R')})",
                color=int(self.bot.config["Bot"]["DEFAULT_COLOR"], 16),
            )
            .set_image(url=data[0])
            .set_footer(
                text=f"Requested By: {self.message.author.name} ({self.message.author.id})"
            )
        )

    def update_buttons(self):
        self.first.disabled = False
        self.prev.disabled = False
        self.next.disabled = False
        self.last.disabled = False

        if self.data["idx"] == 0:
            self.first.disabled = True
            self.prev.disabled = True

        if (self.data["idx"] + 1) == self.data["count"]:
            self.next.disabled = True
            self.last.disabled = True

        self.page.label = f"{self.data['idx'] + 1}/{self.data['count']}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.message.author:
            return True

        await interaction.response.send_message(
            "Please invoke the command yourself.", ephemeral=True
        )
        return False  # love u type-checker

    @ui.button(label="<<")
    async def first(self, itx: discord.Interaction, _: ui.Button[Self]):
        await self._goto(0, itx)

    @ui.button(label="<")
    async def prev(self, itx: discord.Interaction, _: ui.Button[Self]):
        await self._goto(self.data["idx"] - 1, itx)

    @ui.button(label="\u200b")
    async def page(self, itx: discord.Interaction, _: ui.Button[Self]):
        modal = SkipToPage.with_data(self.data["count"])
        await itx.response.send_modal(modal)
        await modal.wait()

        await self._goto(int(modal.page.value) - 1, itx)

    @ui.button(label=">")
    async def next(self, itx: discord.Interaction, _: ui.Button[Self]):
        await self._goto(self.data["idx"] + 1, itx)

    @ui.button(label=">>")
    async def last(self, itx: discord.Interaction, _: ui.Button[Self]):
        await self._goto(self.data["count"] - 1, itx)


class RotatingWebhook:
    def __init__(self, webhooks: list[discord.Webhook]) -> None:
        self.webhooks = webhooks
        self.index = 0

    def get(self) -> discord.Webhook:
        if len(self.webhooks) <= self.index:
            self.index = 0

        self.index += 1

        return self.webhooks[self.index - 1]

    @property
    def send(self):
        return self.get().send


class Logger(BaseCog):
    def __init__(self, bot: "Bot"):
        super().__init__(bot)

        if self.bot.is_dev:
            raise Exception(
                "Please disable the cog `Logger`, this cog isn't intended in an development enviroment."
            )

        self.webhooks = RotatingWebhook(
            [
                discord.Webhook.from_url(URL, session=self.bot.session)
                for URL in self.CONFIG["AVATAR_LOGGING"]["WEBHOOKS"]
            ]
        )

        # the docs say the ratelimits are 30 requests per 10 seconds, just to be safe i'm leaving a bit of headroom.
        self.ratelimit_cooldown = commands.CooldownMapping.from_cooldown(  # pyright: ignore[reportUnknownMemberType]
            15,
            1,
            lambda avatar: avatar.key,  # pyright: ignore[reportUnknownLambdaType,reportUnknownMemberType]
        )

    async def upload_avatar(
        self,
        member: discord.Member,
        file: discord.Asset,
        changed_at: datetime = discord.utils.utcnow(),
    ):
        retry = self.ratelimit_cooldown.update_rate_limit(file)  # pyright: ignore[reportUnknownMemberType]
        if retry:
            await asyncio.sleep(retry)
            await self.upload_avatar(member, file, changed_at)

        async with self.bot.session.get(file.url) as req:
            if req.status != 200:
                logger.error(f"Failed to fetch {member}'s avatar. {await req.text()}")
                return

            resp = await req.read()
            content_type = req.headers.get("Content-Type", "image/png")
            data = BytesIO(resp)

            if data.getbuffer().nbytes > GUILD_FILESIZE_LIMIT:
                logger.error(
                    f"AVATAR LIMIT EXCEEDED, avatar size: {data.getbuffer().nbytes}"
                )
                return

            # not always accurate but it is in our usecase.
            file_ext = content_type.partition("/")[-1:][0]

            resp = await self.webhooks.send(
                f"{member.id}\n{changed_at.timestamp()}",
                file=discord.File(data, f"{member.id}.{file_ext}"),
                wait=True,
            )

            if resp:
                await self.bot.pool.execute(
                    """
                INSERT INTO avatar_history (
                    user_id,
                    changed_at,
                    avatar_url
                ) VALUES ($1, $2, $3)
                """,
                    member.id,
                    changed_at,
                    resp.attachments[0].url,
                )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        members = await guild.chunk() if not guild.chunked else guild.members

        for member in members:
            if member.mutual_guilds or member is guild.me:
                continue

            await self.upload_avatar(member, member.display_avatar)

    @commands.Cog.listener()
    async def on_member_avatar_update(
        self, before: discord.Member, after: discord.Member
    ):
        avatar = None
        if before.guild_avatar != after.guild_avatar:
            avatar = after.guild_avatar
        elif before.avatar != after.avatar:
            avatar = after.avatar

        if not avatar:
            avatar = after.display_avatar

        await self.upload_avatar(after, avatar)

    @commands.Cog.listener()
    async def on_member_name_update(self, before: discord.User, _: discord.User):
        await self.bot.pool.execute(
            """
        INSERT INTO username_history (user_id, time_changed, name)
            VALUES ($1, $2, $3)
        """,
            before.id,
            discord.utils.utcnow(),
            before.name,
        )

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name != after.name:
            self.bot.dispatch("member_name_update", before, after)

        if before.avatar != after.avatar:
            self.bot.dispatch("member_avatar_update", before, after)

    @commands.command(aliases=["avatars", "avyh"])
    async def pfps(
        self,
        ctx: commands.Context["Bot"],
        user: discord.User = commands.Author,
    ):
        try:
            view = await AvatarPaginator().populate_data(
                ctx.bot,
                ctx.message,
                user,
            )
        except NoAvatarData:
            await ctx.send("No avatar found")
        else:
            await ctx.send(
                embed=view.create_embed(),
                view=view,
            )


async def setup(bot: Bot):
    await bot.add_cog(Logger(bot))

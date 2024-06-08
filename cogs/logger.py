from __future__ import annotations

import discord
from discord.ext import commands

import asyncio

from datetime import datetime
from io import BytesIO

from typing import TYPE_CHECKING

from utils.paginator import ChunkedPaginator
from . import BaseCog, logger

if TYPE_CHECKING:
    from typing import Any
    from typing_extensions import Self

    from utils.subclasses import Bot

    UserOrMember = discord.User | discord.Member


GUILD_FILESIZE_LIMIT = 25 * 1024 * 1024


class NoAvatarData(Exception): ...


class AvatarPaginator(ChunkedPaginator[tuple[str, datetime]]):
    def __init__(
        self,
        bot: "Bot",
        user: discord.User,
        message: discord.Message,
        *args: Any,
        **kwargs: Any,
    ):
        self.bot = bot
        self.user = user
        self.message = message

        super().__init__(*args, **kwargs)

    @classmethod
    async def populate_data(
        cls,
        bot: Bot,
        message: discord.Message,
        user: discord.User,
        *args: Any,
        **kwargs: Any,
    ) -> Self:
        count = await bot.pool.fetchval(
            """
            SELECT
                COUNT(*)
            FROM avatar_history
            WHERE
                user_id = $1
                AND changed_at < $2;
        """,
            user.id,
            message.created_at,
        )

        if count <= 0:
            raise NoAvatarData

        return cls(
            bot,
            user,
            message,
            *args,
            limit_to_user=message.author,
            count=count,
            **kwargs,
        )

    async def fetch_chunk(self, chunk: int) -> list[tuple[str, datetime]]:
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
            self.user.id,
            self.message.created_at,
            self.per_chunk,
            chunk,
        )

        return [
            (
                record["avatar_url"],
                record["changed_at"],
            )
            for record in records
        ]

    async def format_page(self, page: tuple[str, datetime]) -> dict[str, Any]:
        embed = (
            discord.Embed(
                title=f"{self.user.name}'s Avatar History",
                description=f"Changed At: {discord.utils.format_dt(page[1])} ({discord.utils.format_dt(page[1], 'R')})",
                color=int(self.bot.config["Bot"]["DEFAULT_COLOR"], 16),
            )
            .set_image(url=page[0])
            .set_footer(
                text=f"Requested By: {self.message.author.name} ({self.message.author.id})"
            )
        )

        return {"embed": embed}


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
        member: UserOrMember,
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
    async def on_member_avatar_update(self, before: UserOrMember, after: UserOrMember):
        avatar = None
        if (
            isinstance(before, discord.Member)
            and isinstance(after, discord.Member)
            and before.guild_avatar != after.guild_avatar
        ):
            avatar = after.guild_avatar
        elif before.avatar != after.avatar:
            avatar = after.avatar

        if not avatar:
            avatar = after.display_avatar

        await self.upload_avatar(after, avatar)

    @commands.Cog.listener()
    async def on_member_name_update(self, before: UserOrMember, _: UserOrMember):
        await self.bot.pool.execute(
            """
        INSERT INTO username_history (user_id, time_changed, name)
            VALUES ($1, $2, $3)
        """,
            before.id,
            discord.utils.utcnow(),
            before.name,
        )

    @commands.Cog.listener("on_user_update")
    @commands.Cog.listener("on_member_update")
    async def on_user_or_member_update(
        self,
        before: UserOrMember,
        after: UserOrMember,
    ):
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
            paginator = await AvatarPaginator.populate_data(
                ctx.bot,
                ctx.message,
                user,
            )
        except NoAvatarData:
            await ctx.send("No avatar found")
        else:
            await paginator.send(ctx)


async def setup(bot: Bot):
    await bot.add_cog(Logger(bot))

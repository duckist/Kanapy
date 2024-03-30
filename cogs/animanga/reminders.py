import discord
from discord import ui
from discord.ext import tasks

from utils.constants import BELL
from libs.livechart import LiveChartClient, Anime

from .. import BaseCog, logger
from .frontend import ReminderButton

from typing import TYPE_CHECKING, Optional, TypedDict

if TYPE_CHECKING:
    from utils.subclasses import Bot


class ReminderData(TypedDict):
    titles: list[Anime]
    currently_sleeping_for: Optional[Anime]


class ReminderCog(BaseCog):
    def __init__(self, bot: "Bot") -> None:
        super().__init__(bot)
        self.client = LiveChartClient()
        self.titles = []

    @tasks.loop(hours=1)
    async def fetch_titles(self):
        titles = list(
            filter(
                lambda title: title["premiere"] > discord.utils.utcnow(),
                await self.client.fetch_today(),
            )
        )

        if not titles:
            titles = list(
                filter(
                    lambda title: title["premiere"] > discord.utils.utcnow(),
                    await self.client.fetch_tomorrow(),
                )
            )

        self.titles = titles
        logger.info(f"Fetched the titles, got {len(titles)} titles.")

    async def remind_title(
        self,
        anime: Anime,
    ):
        assert anime["anilist_id"]
        users = await self.bot.pool.fetch(
            "SELECT user_id FROM anime_reminders WHERE anilist_id = $1",
            anime["anilist_id"],
        )

        if not users:
            return

        user_ids = [user["user_id"] for user in users]
        logger.info(f"Sending reminders to {user_ids} users about {anime}.")

        users = [
            self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            for user_id in user_ids
        ]

        embed = discord.Embed(
            title=(
                f"{BELL} Episode {', '.join(anime['episodes'])} of {anime['title']['romaji']} "
                f"({anime['title']['native']}) has premiered {discord.utils.format_dt(anime['premiere'], 'R')}!"
            ),
        ).set_thumbnail(url=anime["thumbnail"])

        for user in users:
            view = ui.View(timeout=None)
            view.add_item(
                ReminderButton(
                    True,
                    anime["anilist_id"],
                    user.id,
                )
            )

            await user.send(embed=embed, view=view)

    @tasks.loop(minutes=5)
    async def send_out_reminders(self):
        titles = self.titles

        for title in titles:
            logger.info(
                f"Found a new title: {title['title']['romaji']!r}, checking if there are any users interested."
            )

            users = await self.bot.pool.fetchval(
                "SELECT COUNT(*) FROM anime_reminders WHERE anilist_id = $1",
                title["anilist_id"],
            )

            if not users:
                logger.info(f"No user interested in {title['title']['romaji']!r}.")
                continue

            logger.info(
                f"Sleeping for {title['premiere']} seconds, for the title {title['title']['romaji']!r} and for the users {users}."
            )

            await discord.utils.sleep_until(title["premiere"])
            await self.remind_title(title)

    @send_out_reminders.before_loop
    async def before_send_out_reminders(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        self.fetch_titles.start()
        self.send_out_reminders.start()

    async def cog_unload(self):
        self.fetch_titles.stop()
        self.send_out_reminders.stop()
        await self.client.session.close()

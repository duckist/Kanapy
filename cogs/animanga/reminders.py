import discord
from discord import ui
from discord.ext import tasks

from utils.constants import BELL
from libs.livechart import LiveChartClient, Anime

from .. import BaseCog, logger
from .frontend import ReminderButton

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.subclasses import Bot


class ReminderCog(BaseCog):
    def __init__(self, bot: "Bot") -> None:
        super().__init__(bot)
        self.client = LiveChartClient()
        self.titles: list[Anime] = []

    def restart_reminders_watcher(self):
        if self.reminders_watcher.is_running():
            self.reminders_watcher.cancel()

        self.reminders_watcher.start()

    @tasks.loop(hours=1)
    async def fetch_titles(self):
        titles = await self.client.fetch_today(ignore_old=True)

        if len(titles) <= 3:
            titles = await self.client.fetch_tomorrow(ignore_old=True)

        if len(titles) <= 3:
            titles += await self.client.fetch_titles_after_day(2, ignore_old=True)

        if any(
            new_title
            for new_title, old_title in zip(titles, self.titles)
            if new_title["premiere"] != old_title["premiere"]
        ):
            self.restart_reminders_watcher()

        self.titles = titles
        logger.info(f"Fetched {len(titles)} titles.")

    async def send_reminders_for(self, anime: Anime):
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
    async def reminders_watcher(self):
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
                f"Sleeping until {title['premiere']}. title={title['title']['romaji']!r}, {users=}"
            )

            await discord.utils.sleep_until(title["premiere"])
            await self.send_reminders_for(title)

    @reminders_watcher.before_loop
    async def before_reminders_watcher(self):
        await self.bot.wait_until_ready()

    async def cog_load(self):
        self.fetch_titles.start()
        self.reminders_watcher.start()

    async def cog_unload(self):
        self.fetch_titles.cancel()
        self.reminders_watcher.cancel()
        await self.client.session.close()

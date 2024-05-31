from __future__ import annotations

import discord
from discord.ext import tasks

from utils.constants import BELL
from libs.livechart import LiveChartClient, Anime

from .. import BaseCog, logger

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from utils.subclasses import Bot


class AnimangaReminders(BaseCog):
    def __init__(self, bot: Bot) -> None:
        super().__init__(bot)
        self.client = LiveChartClient()
        self.titles: list[Anime] = []
        self.currently_sleeping_for: Optional[int] = None

    async def toggle_reminder_for(
        self,
        user_id: int,
        anime_id: int,
    ) -> bool:
        result = await self.bot.pool.fetchval(
            "SELECT toggle_reminder($1, $2)",
            user_id,
            anime_id,
        )

        if anime_id == self.currently_sleeping_for:
            self.restart_user_reminders()

        return result == 1

    @tasks.loop(hours=1)
    async def livechart_watcher(self):
        titles = await self.client.fetch_today(ignore_old=True)

        if len(titles) <= 3:
            titles = await self.client.fetch_tomorrow(ignore_old=True)

        if len(titles) <= 3:
            titles += await self.client.fetch_titles_after_day(2, ignore_old=True)

        if titles != self.titles:
            self.restart_user_reminders()

        self.titles = titles

    async def send_reminders_out_for(self, anime: Anime):
        users = await self.bot.pool.fetch(
            "SELECT user_id FROM anime_reminders WHERE anilist_id = $1",
            anime["anilist_id"],
        )

        if not users:
            return

        user_ids = [user["user_id"] for user in users]
        logger.info(
            f"Sending reminders to {user_ids} users about {anime['title']['romaji']!r}."
        )

        users = [
            self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            for user_id in user_ids
        ]

        embed = discord.Embed(
            title=(
                f"{BELL} Episode {', '.join(anime['episodes'])} of {anime['title']['romaji']} "
                f"({anime['title']['native']!r}) has premiered {discord.utils.format_dt(anime['premiere'], 'R')}!"
            ),
        ).set_thumbnail(url=anime["thumbnail"])

        for user in users:
            await user.send(embed=embed)

    @tasks.loop(minutes=5)
    async def user_reminders(self):
        titles = self.titles

        for title in titles:
            users = await self.bot.pool.fetchval(
                "SELECT COUNT(*) FROM anime_reminders WHERE anilist_id = $1",
                title["anilist_id"],
            )

            if not users:
                logger.info(f"No user interested in {title['title']['romaji']!r}.")
                continue

            logger.info(
                f"{users} users are interested in {title['title']['romaji']!r}, episode premieres at {title['premiere']}"
            )

            self.currently_sleeping_for = title["anilist_id"]
            await discord.utils.sleep_until(title["premiere"])

            await self.send_reminders_out_for(title)

            self.currently_sleeping_for = None

    @user_reminders.before_loop
    async def before_reminders_watcher(self):
        await self.bot.wait_until_ready()

    def restart_user_reminders(self):
        self.user_reminders.restart()
        self.currently_sleeping_for = None

    async def cog_load(self):
        """
        self.livechart_watcher.start()
        self.user_reminders.start()
        """

    async def cog_unload(self):
        """
        self.user_reminders.cancel()
        self.livechart_watcher.cancel()

        await self.client.session.close()
        """

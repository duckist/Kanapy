from __future__ import annotations

import bs4
import aiohttp

from datetime import datetime, timezone

from typing import Any, Optional, TypedDict


class Title(TypedDict):
    native: str
    romaji: str


class Anime(TypedDict):
    id: int
    anilist_id: Optional[int]
    title: Title
    thumbnail: str
    episodes: list[str]
    premiere: datetime


class NotFound(Exception): ...


class LiveChartClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def get_soup(self) -> bs4.BeautifulSoup:
        async with self.session.get(
            "https://www.livechart.me/schedule?layout=full",
        ) as req:
            if req.status != 200:
                raise Exception(
                    f"Failed to fetch schedule, recieved a {req.status} Status Code."
                )

            return bs4.BeautifulSoup(
                await req.text(),
                "html.parser",
            )

    def find(
        self,
        soup: bs4.BeautifulSoup | bs4.Tag,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[bs4.Tag]:
        element = soup.find(*args, **kwargs)

        if element and isinstance(element, bs4.Tag):
            return element

    def find_all(
        self,
        soup: bs4.BeautifulSoup | bs4.Tag,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[list[bs4.Tag]]:
        elements = soup.find_all(*args, **kwargs)

        if elements:
            return elements

    def parse_title(self, article: bs4.Tag) -> Anime:
        attrs = article.attrs
        time = self.find(article, "time", {"data-controller": "countdown"})

        anilist_icon = self.find(
            article, "a", {"class": "lc-anime-card--related-links--icon anilist"}
        )

        thumbnail = self.find(article, "img")

        episodes = None
        overlay = self.find(article, "div", {"class": "lc-anime-card--poster-overlays"})
        if overlay:
            episodes = self.find(
                article, "span"
            )  # the only span object is the episode number

        return {
            "id": int(attrs["data-anime-id"]),
            "anilist_id": int(
                anilist_icon.attrs["href"].removeprefix("https://anilist.co/anime/")
            )
            if anilist_icon
            else None,
            "title": {
                "native": attrs["data-native"],
                "romaji": attrs["data-romaji"],
            },
            "thumbnail": thumbnail.attrs["src"] if thumbnail else "N/A",
            "episodes": episodes.text.removeprefix("EP").split("–") if episodes else [],
            "premiere": datetime.fromtimestamp(
                int(time.attrs["data-timestamp"]),
                tz=timezone.utc,
            )
            if time
            else datetime.fromtimestamp(
                0,
                tz=timezone.utc,
            ),
        }

    async def fetch_titles_after_day(self, day: int) -> list[Anime]:
        soup = await self.get_soup()
        twenty_four_hour_periods = self.find_all(
            soup, "div", {"data-controller": "schedule-day"}
        )
        if not twenty_four_hour_periods:
            raise NotFound

        articles = self.find_all(
            twenty_four_hour_periods[day],
            "article",
            {"class": "lc-anime", "data-controller": "anime-card"},
        )
        if not articles:
            raise NotFound

        return sorted(
            list(map(self.parse_title, articles)), key=lambda anime: anime["premiere"]
        )

    async def fetch_today(self):
        return await self.fetch_titles_after_day(0)

    async def fetch_tomorrow(self):
        return await self.fetch_titles_after_day(1)

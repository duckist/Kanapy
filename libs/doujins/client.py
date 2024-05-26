from __future__ import annotations

import cloudscraper  # pyright: ignore[reportMissingTypeStubs]

from utils.functions import run_in_executor

from .types import Gallery
from .constants import BASE_URL

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from typing import Any, Optional

T = TypeVar("T")


class Route:
    def __init__(
        self,
        URL: str,
        path: str,
        *,
        method: str = "GET",
        params: dict[str, Any] = {},
    ):
        self.URL = URL
        self.path = path
        self.params = params
        self.method = method

    @property
    def url(self):
        return f"{self.URL}{self.path.format(**self.params)}"

    def __str__(self) -> str:
        return (
            f"<Route path={self.path!r} method={self.method!r} params={self.params!r}>"
        )


class DoujinClient:
    def __init__(self) -> None:
        self.scraper = cloudscraper.create_scraper()  # pyright: ignore[reportUnknownMemberType]

    @run_in_executor
    def query(self, route: Route):
        with self.scraper.get(route.url) as req:
            if req.status_code == 403:
                raise Exception("Cloudflare Blocked")
            elif req.status_code == 404:
                return None
            elif req.status_code != 200:
                raise Exception(
                    f"Recieved an {req.status_code} while trying to query {route.path!r}"
                )

            return req.json()

    async def fetch_doujin(
        self,
        doujin: int,
    ) -> Optional[Gallery]:
        route = Route(
            BASE_URL,
            "/api/gallery/{doujin}",
            params={
                "doujin": doujin,
            },
        )

        data = await self.query(route)
        if not data:
            return

        return Gallery.from_data(data)

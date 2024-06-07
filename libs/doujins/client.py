from __future__ import annotations

import aiohttp  # pyright: ignore[reportMissingTypeStubs]

from .types import Gallery
from .constants import BASE_URL

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Optional


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
    def __init__(
        self,
        session: aiohttp.ClientSession,
        flare_solver: str,
    ) -> None:
        self.FLARE_SOLVER = flare_solver
        self.session = session
        self.query_metadata: Any = {}

    @classmethod
    async def new(cls, flare_solver: str) -> DoujinClient:
        session = aiohttp.ClientSession()

        return cls(
            session=session,
            flare_solver=flare_solver,
        )

    async def _renew_cloudflare_token(
        self,
        *,
        retries: int = 0,
        timeout: int = 60,
    ) -> None:
        async with self.session.post(
            f"{self.FLARE_SOLVER}/v1",
            json={
                "cmd": "request.get",
                "url": f"{BASE_URL}/404",
                "maxTimeout": timeout * 1000,
            },
        ) as req:
            data = await req.json()
            if req.status != 200:
                if retries <= 3:
                    return await self._renew_cloudflare_token(
                        retries=retries + 1,
                        timeout=timeout,
                    )

                raise Exception(
                    f"Failed to renew cloudflare token, recieved a {req.status} Status Code."
                )

            self.query_metadata = {
                "headers": {
                    "User-Agent": data["solution"]["userAgent"],
                    **data["solution"]["headers"],
                },
                "cookies": {
                    cookie["name"]: cookie["value"]
                    for cookie in data["solution"]["cookies"]
                },
            }

    async def query(self, route: Route) -> Optional[dict[str, Any]]:
        async with self.session.get(
            route.url,
            **self.query_metadata,
        ) as req:
            if req.status == 403:
                await self._renew_cloudflare_token()
                return await self.query(route)
            elif req.status == 404:
                return None
            elif req.status != 200:
                raise Exception(
                    f"Recieved an {req.status} while trying to query {route.path!r}"
                )

            return await req.json()

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

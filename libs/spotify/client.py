import discord
import json

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Optional, overload

from .. import logger
from .types import (
    AccessToken,
    Album,
    Playlist,
    Podcast,
    Song,
    Artist,
    Topic,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession


class InvalidToken(Exception): ...


HEADER_TEMPLATE = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en",
    "app-platform": "WebPlayer",
    "content-type": "application/json;charset=UTF-8",
    "Host": "api-partner.spotify.com",
    "Origin": "https://open.spotify.com",
    "Referer": "https://open.spotify.com/",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "TE": "trailers",
    "spotify-app-version": "1.2.18.326.g686ebe89",
    # "client-token": "" # it doesn't seem to required so I don't care.
}

# fmt: off

class SearchType(Enum):
    tracksV2  = {"operationName": "searchTracks",       "sha256Hash": "1d021289df50166c61630e02f002ec91182b518e56bcd681ac6b0640390c0245"}
    artists   = {"operationName": "searchArtists",      "sha256Hash": "4e7cdd33163874d9db5e08e6fabc51ac3a1c7f3588f4190fc04c5b863f6b82bd"}
    albums    = {"operationName": "searchAlbums",       "sha256Hash": "37197f541586fe988541bb1784390832f0bb27e541cfe57a1fc63db3598f4ffd"}
    playlists = {"operationName": "searchPlaylists",    "sha256Hash": "87b755d95fd29046c72b8c236dd2d7e5768cca596812551032240f36a29be704"}
    podcasts  = {"operationName": "searchPodcasts",     "sha256Hash": "86fd462d46e3bfd7d37fdf5409176196af720c2d3d3eb60307e6490781d8d184"}

# fmt: on


def parse_url(raw: str) -> Optional[str]:
    cnt = raw.split(":")
    if len(cnt) > 2:
        domain, *rest = cnt
        return f"https://open.{domain}.com/{'/'.join(rest)}"


def parse_artist_obj(payload: dict[str, Any]) -> Optional[Artist]:
    if payload:
        return {  # type: ignore
            "name": payload.get("profile", {}).get("name"),
            "url": parse_url(payload.get("uri", "")),
            "is_verified": payload.get("profile", {}).get("verified", None),
        }


def parse_album_obj(payload: dict[str, Any]) -> Optional[Album]:
    if payload:
        return {
            "name": payload.get("name", "N/A"),
            "url": parse_url(payload.get("uri", "")),
            "artists": list(
                map(
                    parse_artist_obj,
                    payload.get("artists", {}).get("items", []),  # type: ignore
                )
            ),
        }


def parse_playlist_obj(payload: dict[str, Any]) -> Optional[Playlist]:
    if payload:
        data = {
            "name": payload.get("name"),
            "url": parse_url(payload.get("uri", "")),
            "description": payload.get("description", ""),
        }

        owner = payload.get("ownerV2", {}).get("data")
        if owner:
            data["owner"] = {
                "username": owner.get("username"),
                "display_name": owner.get("name"),
                "url": parse_url(owner.get("uri", "")),
            }

        return data  # type: ignore


def parse_podcast_obj(payload: dict[str, Any]) -> Optional[Podcast]:
    p = payload["data"]

    return {  # type: ignore
        "name": p["name"],
        "url": parse_url(p["uri"]),
        "publisher": p.get("publisher", {}).get("name", "UNKNOWN"),
        "topics": map(parse_topic, p.get("topics", {}).get("items", [])),
    }


def parse_songs(payload: dict[str, Any]) -> Optional[Song]:
    track: dict[str, Any] = payload.get("item", {}).get("data", {})
    if track:
        return {
            "track_name": track.get("name"),
            "track_url": parse_url(track.get("uri", "")),
            "album": parse_album_obj(track.get("albumOfTrack", {})),  # type: ignore
            "artists": list(
                map(
                    parse_artist_obj,
                    track.get("artists", {}).get("items", []),  # type: ignore
                )
            ),
        }


def parse_topic(payload: dict[str, Any]) -> Optional[Topic]:
    if payload:
        return {  # type: ignore
            "title": payload["title"],
            "url": parse_url(payload["uri"]),
        }


def parse_artists(payload: dict[str, Any]):
    artist = payload.get("data")
    if artist:
        return parse_artist_obj(artist)


def parse_albums(payload: dict[str, Any]):
    album = payload.get("data")
    if album:
        return parse_album_obj(album)


def parse_playlists(payload: dict[str, Any]):
    playlist = payload.get("data")
    if playlist:
        return parse_playlist_obj(playlist)


def parse_podcast(payload: dict[str, Any]) -> Optional[Podcast]:
    if payload:
        return parse_podcast_obj(payload)  # type: ignore


strategy = {
    SearchType.tracksV2: parse_songs,
    SearchType.artists: parse_artists,
    SearchType.albums: parse_albums,
    SearchType.playlists: parse_playlists,
    SearchType.podcasts: parse_podcast,
}


class SpotifyClient:
    def __init__(self, session: "ClientSession"):
        self.session = session
        self.token: Optional[AccessToken] = None

    @overload
    async def search(
        self, query: str, *, search_type: Literal[SearchType.tracksV2]
    ) -> list[Song]: ...

    @overload
    async def search(
        self, query: str, *, search_type: Literal[SearchType.artists]
    ) -> list[Artist]: ...

    @overload
    async def search(
        self, query: str, *, search_type: Literal[SearchType.albums]
    ) -> list[Album]: ...

    @overload
    async def search(
        self, query: str, *, search_type: Literal[SearchType.playlists]
    ) -> list[Playlist]: ...

    @overload
    async def search(
        self, query: str, *, search_type: Literal[SearchType.podcasts]
    ) -> list[Podcast]: ...

    async def search(
        self, query: str, *, search_type: SearchType, offset: int = 0, limit: int = 10
    ) -> Any:
        if (self.token is None) or (
            self.token["accessTokenExpirationTimestampMs"]
            < discord.utils.utcnow().timestamp()
        ):
            await self.renew_token()
        try:
            resp = await self._search(
                query, search_type=search_type, offset=offset, limit=limit
            )
        except InvalidToken:
            await (
                self.renew_token()
            )  # because the token timesout when due to inactivity
            return await self._search(
                query, search_type=search_type, offset=offset, limit=limit
            )
        else:
            return resp

    async def _search(
        self,
        query: str,
        *,
        search_type: SearchType = SearchType.tracksV2,
        offset: int = 0,
        limit: int = 10,
    ) -> Any:
        async with self.session.get(
            "https://api-partner.spotify.com/pathfinder/v1/query",
            params={
                "operationName": search_type.value["operationName"],
                "variables": json.dumps(
                    {"searchTerm": query, "offset": offset, "limit": limit}
                ),
                "extensions": json.dumps(
                    {
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": search_type.value["sha256Hash"],
                        }
                    }
                ),
            },
            headers={
                **HEADER_TEMPLATE,
                "authorization": f"Bearer {self.token['accessToken']}",  # type: ignore
            },
        ) as req:
            if req.status == 401:
                raise InvalidToken(await req.text())
            elif req.status != 200:
                raise Exception(await req.text())

            raw_data = await req.json()
            if raw_data.get(
                "errors"
            ):  # for some reason spotify still returns a 200 for errors.
                logger.error(f"Spotify returned an error: {raw_data}")
                raise Exception(raw_data)

            data = (
                raw_data.get("data", {}).get("searchV2", {}).get(search_type.name, {})
            )
            if not data:
                logger.info(f"No data found for the query: '{query}' ({search_type}).")
                return []

            strat = strategy.get(search_type)
            if not strat:
                raise NotImplementedError

            return list(map(strat, data.get("items")))  # type: ignore

    async def renew_token(self) -> None:
        async with self.session.get("https://open.spotify.com/get_access_token") as req:
            if req.status == 401:
                raise InvalidToken(await req.text())
            elif req.status != 200:
                logger.error(
                    f"Tried to get Spotify access token but it failed with a response of: ({req.status}) {await req.text()}"
                )
                raise Exception

            self.token = await req.json()

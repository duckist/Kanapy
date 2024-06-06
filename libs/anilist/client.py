from discord import Interaction, app_commands
from aiohttp import ClientSession

from typing import Any, Optional, TYPE_CHECKING

from utils import cutoff

from .utils import QUERY_PATTERN
from .types import SearchType, Media, MediaResponse, AccessToken

if TYPE_CHECKING:
    from utils.subclasses import Bot

SEARCH_QUERY = """
query ($search: String, $type: MediaType) {
  Page(perPage: 10) {
    media(search: $search, type: $type, sort: POPULARITY_DESC) {
      id
      title {
        romaji
      }
    }
  }
}
"""

FETCH_QUERY = """
query ($id: Int, $search: String, $type: MediaType) {
  Media(id: $id, search: $search, type: $type, sort: POPULARITY_DESC) {
    title {
      romaji
    }
    coverImage {
      extraLarge
      color
    }
    trailer {
      site
      id
    }
    description(asHtml: false)
    nextAiringEpisode {
      id
    }
    episodes
    id
    genres
    averageScore
    duration
    chapters
    status
    bannerImage
    siteUrl
    isAdult
    relations {
      edges {
        relationType(version: 2)
        node {
          id
          title {
            romaji
          }
          type
        }
      }
    }
    studios {
      edges {
        node {
          name
          siteUrl
        }
        isMain
      }
    }
  }
}
"""


BASE_URL = "https://graphql.anilist.co/"
SEARCH_TYPE = {
    "anime": SearchType.ANIME,
    "manga": SearchType.MANGA,
}


class AniList:
    def __init__(
        self,
        session: ClientSession,
        *,
        anilist_id: str,
        anilist_secret: str,
    ):
        self.session = session
        self.ANILIST_ID = anilist_id
        self.ANILIST_SECRET = anilist_secret

    @staticmethod
    async def query(
        session: ClientSession,
        *,
        URL: str = BASE_URL,
        **kwargs: Any,
    ):
        async with session.post(URL, **kwargs) as req:
            if req.status != 200:
                raise Exception(
                    f"Recieved a non 200 response: {req.status=}\n{await req.text()}"
                )

            data = await req.json()

            if data.get("errors"):
                raise Exception(
                    f"Search yielded errors:\n{kwargs=}\n{await req.text()}"
                )

            return data.get("data") or data

    @classmethod
    async def search_auto_complete(
        cls,
        interaction: Interaction["Bot"],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """
        A wrapper around the `search` function for slash auto-complete.

        Parameteres
        ------------
        interaction: Interaction["Bot]
            The Interaction instance.

        current: str
            The search query.
        """

        assert (
            isinstance(interaction.command, app_commands.Command)
            and interaction.command.parent
        )

        req = await cls.query(
            interaction.client.session,
            json={
                "query": SEARCH_QUERY,
                "variables": {
                    "search": current or None,
                    "type": SEARCH_TYPE[interaction.command.parent.name],
                },
                "search_type": SEARCH_TYPE[interaction.command.parent.name].value,
            },
        )

        data = req.get("Page", {}).get("media")
        if not data:
            return []

        return [
            app_commands.Choice(
                name=cutoff(media["title"]["romaji"], 100),
                value=cutoff(
                    media["title"]["romaji"],
                    100,
                    ending=f" (ID: {media['id']})",
                ),
            )
            for media in data
        ]

    async def fetch(
        self,
        search: str,
        *,
        search_type: SearchType,
    ) -> Optional[Media]:
        """
        Fetches information about a Series.

        Parameteres
        ------------
        search: str
            The search query.

        search_type: SearchType
            An Enum of either ANIME or MANGA.
        """

        variables = {
            "type": search_type.name,
        }

        if match := QUERY_PATTERN.fullmatch(search):
            variables["id"] = int(match.group(1))  # pyright: ignore[reportArgumentType]
        else:
            variables["search"] = search

        req = await self.query(
            self.session,
            json={
                "query": FETCH_QUERY,
                "variables": variables,
            },
        )

        data: Optional[MediaResponse] = req.get("Media")
        if not data:
            return None

        return Media.from_data(
            data,
            search_type=search_type,
        )

    async def get_access_token(self, token: str) -> AccessToken:
        """
        Fetches an access token from an authorization code.

        Parameteres
        ------------
        token: str
            The authorization code.
        """

        req = await self.query(
            self.session,
            URL="https://anilist.co/api/v2/oauth/token",
            json={
                "code": token,
                "client_id": self.ANILIST_ID,
                "client_secret": self.ANILIST_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": "https://anilist.co/api/v2/oauth/pin",
            },
        )

        return AccessToken.from_json(req)

    async def fetch_user_id(self, token: str) -> int:
        """
        Fetches the ID of the currently logged in user.

        Parameteres
        ------------
        token: str
            The access token.
        """

        query = """
            query {
                Viewer {
                    id
                }
            }
        """

        req = await self.query(
            self.session,
            json={
                "query": query,
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        return req.get("Viewer", {}).get("id")

    async def get_user_id(self, user: str | int) -> Optional[int]:
        """
        Fetches the ID of a user from their username or ID.

        Parameteres
        ------------
        user: str | int
            The username or ID of the user.
        """

        query = """
            query ($id: Int, $name: String) {
                User (id: $id, name: $name) {
                    id
                }
            }
        """

        variables = {}
        if isinstance(user, int):
            variables["id"] = user
        else:
            variables["name"] = user

        try:
            req = await self.query(
                self.session,
                json={
                    "query": query,
                    "variables": variables,
                },
            )
        except Exception:
            ...
        else:
            return req.get("User", {}).get("id")

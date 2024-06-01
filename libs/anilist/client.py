from discord import Interaction, app_commands
from aiohttp import ClientSession

from typing import Any, Optional, TYPE_CHECKING

from utils import cutoff

from .utils import QUERY_PATTERN
from .types import (
    SearchType,
    Media,
    MediaResponse,
)

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
query ($search: %s, $type: MediaType) {
  Media(%s: $search, type: $type, sort: POPULARITY_DESC) {
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


def format_query(query: str) -> tuple[str, Optional[str]]:
    match = QUERY_PATTERN.fullmatch(query)
    if match:
        return (FETCH_QUERY % ("Int", "id"), match.groups()[0])

    return (FETCH_QUERY % ("String", "search"), None)


BASE_URL = "https://graphql.anilist.co/"
SEARCH_TYPE = {
    "anime": SearchType.ANIME,
    "manga": SearchType.MANGA,
}


class AniList:
    def __init__(self, session: ClientSession):
        self.session = session

    @staticmethod
    async def query(
        session: ClientSession,
        query: str,
        *,
        variables: dict[str, Any] = {},
        search_type: Optional[SearchType] = None,
    ):
        if search_type:
            variables["type"] = search_type.name

        async with session.post(
            BASE_URL,
            json={
                "query": query,
                "variables": variables,
            },
        ) as req:
            if req.status != 200:
                raise Exception(
                    f"Recieved a non 200 response: {req.status=} \n{await req.text()}"
                )

            data = await req.json()

            if data.get("errors"):
                raise Exception(
                    f"Search yielded errors:\n{query=}\n{variables=}\n{await req.text()}"
                )

            return data["data"]

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

        results = await cls.query(
            interaction.client.session,
            SEARCH_QUERY,
            variables={
                "search": current or None,
            },
            search_type=SEARCH_TYPE[interaction.command.parent.name],
        )

        _id = " (ID: {series_id})"

        return [
            app_commands.Choice(
                name=cutoff(name, 100),
                value=cutoff(name, 100 - len(_id.format(series_id=series_id)))
                + _id.format(series_id=series_id),
            )
            for series_id, name in results
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

        query, animanga_id = format_query(search)

        req = await self.query(
            self.session,
            query,
            variables={
                "search": animanga_id or search,
            },
            search_type=search_type,
        )

        data: Optional[MediaResponse] = req.get("Media")
        if not data:
            return None

        return Media.from_data(
            data,
            search_type=search_type,
        )

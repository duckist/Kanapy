import re

from discord import Interaction, app_commands
from aiohttp import ClientSession

from typing import Any, Optional, TYPE_CHECKING

from utils import cutoff
from .. import logger

from .types import (
    FetchResult,
    FetchRequestResult,
    RawRelationEdge,
    Relation,
    SearchType,
    StudioEdge,
    Trailer,
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

QUERY_PATTERN = re.compile(r".* \(ID: ([0-9]+)\)")
TAG_PATTERN = re.compile(
    r"\<(?P<tag>[a-zA-Z]+)(?: href=\"(?P<url>.*)\")?\>(?:(?P<text>[\s\S]+?)\<\/\1\>)?",
    flags=re.M | re.S | re.U,
)


def format_query(query: str) -> tuple[str, Optional[str]]:
    match = QUERY_PATTERN.fullmatch(query)
    if match:
        return (FETCH_QUERY % ("Int", "id"), match.groups()[0])

    return (FETCH_QUERY % ("String", "search"), None)


def formatter(match: re.Match[Any]) -> str:
    items = match.groupdict()
    if items["tag"] == "a":
        return f"[{items['text']}]({items['url']})"
    elif items["tag"] == "br":
        return "\n"
    elif items["tag"] == "i":
        return f"*{items['text']}*"
    elif items["tag"] == "b":
        return f"**{items['text']}**"

    return items["text"]


def cleanup_html(description: str) -> str:
    final, no = TAG_PATTERN.subn(formatter, description)
    if no > 0:
        return cleanup_html(final)

    return final.replace("\n\n", "\n")


def parse_studios(edge: StudioEdge):
    name = edge.get("node", {}).get("name")
    url = edge.get("node", {}).get("siteUrl")
    return {
        "name": name,
        "url": url,
        "formatted": f"[{name}]({url})",
        "main": edge.get("isMain", False),
    }


def parse_relation_edges(edge: RawRelationEdge) -> Relation:
    return {
        "id": edge["node"]["id"],
        "title": edge["node"]["title"]["romaji"],
        "relation_type": edge["relationType"],
        "type": edge["node"]["type"],
    }


def create_trailer_url(data: Trailer) -> str:
    if data["site"] == "youtube":
        return "https://www.youtube.com/watch?v=" + data["id"]
    elif data["site"] == "dailymotion":
        return "https://www.dailymotion.com/video/" + data["id"]

    logger.error(f"Found a different trailer site, data: {data}")
    return ""


class AniList:
    def __init__(self, session: ClientSession):
        self.session = session

    @classmethod
    async def search(
        cls, session: ClientSession, search: str, search_type: SearchType
    ) -> list[tuple[int, str]]:
        """
        Searches for a Series, this won't return any information but rather titles.

        Parameteres
        ------------
        session: ClientSession
            A `aiohttp.ClientSession` object to do the request with.

        search: str
            The search query.

        search_type: SEARCH_TYPE
            An Enum of either ANIME or MANGA.
        """

        req = await session.post(
            "https://graphql.anilist.co/",
            json={
                "query": SEARCH_QUERY,
                "variables": {
                    "search": search if search else None,
                    "type": search_type.name,
                },
            },
        )

        resp = await req.json()
        if resp.get("errors"):
            logger.error(
                f"Search result {search!r} ({search_type.name}) yielded an error: \n{resp}"
            )
            return []

        data = resp.get("data", {}).get("Page", {}).get("media", [])

        return [(result["id"], result["title"]["romaji"]) for result in data]

    @classmethod
    async def search_auto_complete(
        cls,
        interaction: Interaction["Bot"],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """
        A wrapper around the `search` function for auto-completes.

        Parameteres
        ------------
        interaction: discord.Interaction
            The Interaction instance.

        current: str
            The search query.
        """

        assert (
            isinstance(interaction.command, app_commands.Command)
            and interaction.command.parent
        )

        SEARCH_TYPE = {
            "anime": SearchType.ANIME,
            "manga": SearchType.MANGA,
        }

        results = await cls.search(
            interaction.client.session,
            current,
            SEARCH_TYPE[interaction.command.parent.name],
        )

        return [
            app_commands.Choice(
                name=cutoff(name, 100), value=f"{name} (ID: {series_id})"
            )
            for series_id, name in results
        ]

    async def fetch(
        self,
        search: str,
        *,
        search_type: SearchType,
    ) -> Optional[FetchResult]:
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

        req = await self.session.post(
            "https://graphql.anilist.co/",
            json={
                "query": query,
                "variables": {
                    "search": animanga_id or search,
                    "type": search_type.name,
                },
            },
        )

        resp = await req.json()
        if resp.get("errors"):
            return logger.error(
                f"Fetch result {search!r} ({search_type}) yielded an error: \n{resp}"
            )

        data: Optional[FetchRequestResult] = resp.get("data", {}).get("Media")
        if not data:
            return logger.error(data)

        return {  # type: ignore
            **data,
            "type": search_type,
            "title": data.get("title", {}).get("romaji", "N/A"),
            "coverImage": data["coverImage"]["extraLarge"],
            "color": data["coverImage"]["color"],
            "description": cleanup_html(data["description"] or ""),
            "status": data["status"].title().replace("_", " "),
            "trailer": create_trailer_url(data["trailer"]) if data["trailer"] else None,
            "relations": list(map(parse_relation_edges, data["relations"]["edges"])),
            "studios": list(map(parse_studios, data.get("studios", {}).get("edges"))),
        }

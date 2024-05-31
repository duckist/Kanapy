from datetime import datetime
from typing import TypedDict, Literal, Optional, NamedTuple

from enum import Enum

from .utils import cleanup_html


class SearchType(Enum):
    ANIME = 1
    MANGA = 2


class StudioNode(TypedDict):
    name: str
    siteUrl: str


class StudioEdge(TypedDict):
    node: StudioNode
    isMain: bool


class RawStudios(TypedDict):
    edges: list[StudioEdge]


class RawRelationNode(TypedDict):
    id: int
    title: dict[Literal["romaji"], str]
    type: Literal["ANIME"] | Literal["MANGA"]


class RawRelationEdge(TypedDict):
    relationType: str
    node: RawRelationNode


class RawRelations(TypedDict):
    edges: list[RawRelationEdge]


class Trailer(TypedDict):
    site: Literal["youtube", "dailymotion"]
    id: str


class CoverImage(TypedDict):
    extraLarge: str
    color: str


class ParsedNode(TypedDict):
    timeUntilAiring: datetime
    episode: int
    mediaId: int


class MediaResponse(TypedDict):
    id: int
    title: dict[Literal["romaji"], str]
    coverImage: CoverImage
    trailer: Optional[Trailer]
    description: str
    genres: list[str]
    averageScore: int
    episodes: Optional[int]
    duration: Optional[int]
    chapters: Optional[int]
    status: Literal["FINISHED", "RELEASING", "NOT_YET_RELEASED", "CANCELLED", "HIATUS"]
    bannerImage: str
    siteUrl: str
    isAdult: bool
    studios: RawStudios
    relations: RawRelations


class Studios(NamedTuple):
    name: str
    url: str
    formatted: str
    main: bool

    @classmethod
    def from_edge(cls, edge: StudioEdge):
        name = edge.get("node", {}).get("name", "N/A")
        url = edge.get("node", {}).get("siteUrl", "N/A")

        return cls(
            name=name,
            url=url,
            formatted=f"[{name}]({url})",
            main=edge.get("isMain", False),
        )


class Relation(NamedTuple):
    id: int
    type: Literal["ANIME"] | Literal["MANGA"]
    title: str
    relation_type: str

    @classmethod
    def from_edge(cls, edge: RawRelationEdge):
        return cls(
            id=edge["node"]["id"],
            title=edge["node"]["title"]["romaji"],
            relation_type=edge["relationType"],
            type=edge["node"]["type"],
        )


class Media(NamedTuple):
    id: int
    average_score: int | str
    banner_image: Optional[str]
    chapters: Optional[int]
    color: str
    cover_image: str
    description: str
    episodes: Optional[int]
    duration: Optional[int]
    genres: list[str]
    is_adult: bool
    site_url: str
    status: str
    title: str
    trailer: Optional[str]
    next_airing_episode: Optional[ParsedNode]
    type: SearchType
    studios: list[Studios]
    relations: list[Relation]

    @staticmethod
    def _create_trailer_url(data: Trailer) -> str:
        if data["site"] == "youtube":
            return "https://www.youtube.com/watch?v=" + data["id"]
        elif data["site"] == "dailymotion":
            return "https://www.dailymotion.com/video/" + data["id"]

        return ""

    @classmethod
    def from_data(
        cls,
        data: MediaResponse,
        *,
        search_type: SearchType,
    ) -> "Media":
        description = cleanup_html(data.get("description", ""))
        title = data.get("title", {}).get("romaji", "N/A")

        trailer = cls._create_trailer_url(data["trailer"]) if data["trailer"] else None

        relations = [
            Relation.from_edge(edge)
            for edge in data.get("relations", {}).get("edges", [])
        ]

        studios = [
            Studios.from_edge(edge) for edge in data.get("studios", {}).get("edges", [])
        ]

        return cls(
            id=data["id"],
            average_score=data.get("averageScore") or "N/A",
            banner_image=data.get("bannerImage"),
            chapters=data.get("chapters"),
            color=data.get("coverImage", {}).get("color"),
            cover_image=data.get("coverImage", {}).get("extraLarge"),
            description=description,
            episodes=data.get("episodes"),
            duration=data.get("duration"),
            genres=data.get("genres", []),
            is_adult=data.get("isAdult", False),
            site_url=data.get("siteUrl"),
            status=data.get("status", "N/A").title().replace("_", " "),
            title=title,
            trailer=trailer,
            next_airing_episode=data.get("nextAiringEpisode"),
            type=search_type,
            studios=studios,
            relations=relations,
        )

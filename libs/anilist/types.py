from datetime import datetime
from typing import TypedDict, Literal, Optional

from enum import Enum


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


class Studios(TypedDict):
    name: str
    url: str
    formatted: str
    main: bool


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


class Relation(TypedDict):
    id: int
    type: Literal["ANIME"] | Literal["MANGA"]
    title: str
    relation_type: str


class FetchRequestResult(TypedDict):
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


class FetchResult(TypedDict):
    id: int
    averageScore: int
    bannerImage: Optional[str]
    chapters: Optional[int]
    color: str
    coverImage: str
    description: str
    episodes: Optional[int]
    duration: Optional[int]
    genres: list[str]
    isAdult: bool
    siteUrl: str
    status: str
    title: str
    trailer: Optional[str]
    nextAiringEpisode: Optional[ParsedNode]
    type: SearchType
    studios: list[Studios]
    relations: list[Relation]

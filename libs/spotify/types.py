from typing import Optional, TypedDict


class AccessToken(TypedDict):
    clientId: str
    accessToken: str
    accessTokenExpirationTimestampMs: int
    isAnonymous: bool


class Owner(TypedDict):
    username: str
    display_name: str
    url: str


class Topic(TypedDict):
    title: str
    url: str


class Artist(TypedDict):
    name: str
    url: str
    is_verified: Optional[bool]


class Album(TypedDict):
    name: str
    url: str
    artist: list[Artist]


class Song(TypedDict):
    track_name: str
    track_url: str
    album: Album
    artists: list[Artist]


class Playlist(TypedDict):
    name: str
    url: str
    description: str
    owner: Optional[Owner]


class Podcast(TypedDict):
    name: str
    url: str
    topics: list[Topic]
    publisher: str

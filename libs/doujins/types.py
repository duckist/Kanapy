from datetime import datetime

from typing import TypedDict, Literal, NamedTuple, Self, Annotated, Any

from .constants import BASE_URL, CDN_URL

FORMATS = {
    "p": "png",
    "j": "jpg",
    "g": "gif",
}


class Image(TypedDict):
    t: str  # file type
    w: int
    h: int


class ImagesResponse(TypedDict):
    pages: list[Image]
    cover: Image
    thumbnail: Image


class TagResponse(TypedDict):
    id: int
    type: Literal[
        "tag",
        "language",
        "translated",
        "parody",
        "group",
        "category",
    ]
    name: str
    url: str
    count: int


class Title(TypedDict):
    pretty: str
    native: str


class GalleryResponse(TypedDict):
    id: int
    media_id: int
    title: Title
    images: ImagesResponse
    scanlator: str
    upload_date: int
    tags: list[TagResponse]
    num_pages: int
    num_favorites: int


class Tag(NamedTuple):
    id: int
    name: str
    url: str
    total: int


class Gallery(NamedTuple):
    media_id: int
    title: Title
    pages: list[str]
    thumbnail: str
    uploaded_at: datetime
    cover: str
    url: str
    pages_num: int
    favourites: int
    tags: dict[str, list[Tag]]

    def __str__(self) -> str:
        return f"<Gallery title={self.title['pretty']!r} media_id={self.media_id!r}>"

    @staticmethod
    def _construct_urls(nedia_id: int, image: list[Image]) -> list[str]:
        output: list[str] = []
        for idx, img in enumerate(image):
            output.append(
                f"{CDN_URL}/galleries/{nedia_id}/{idx + 1}.{FORMATS.get(img['t'], 'png')}"
            )

        return output

    @staticmethod
    def _parse_tags(tags: list[TagResponse]) -> dict[str, list[Tag]]:
        output: dict[str, list[Tag]] = {}
        for tag in tags:
            output.setdefault(tag["type"], []).append(
                Tag(
                    id=tag["id"],
                    name=tag["name"],
                    url=f"{BASE_URL}{tag['url']}",
                    total=tag["count"],
                )
            )

        return output

    @classmethod
    def from_data(
        cls,
        data: Annotated[dict[str, Any], GalleryResponse],
    ) -> Self:
        return cls(
            media_id=data["media_id"],
            title=data["title"],
            uploaded_at=datetime.fromtimestamp(data["upload_date"]),
            pages=cls._construct_urls(data["media_id"], data["images"]["pages"]),
            thumbnail=f"{CDN_URL}/galleries/{data['media_id']}/thumbnail.{FORMATS.get(data['images']['thumbnail']['t'], 'png')}",
            cover=f"{CDN_URL}/galleries/{data['media_id']}/cover.{FORMATS.get(data['images']['cover']['t'], 'png')}",
            url=f"{BASE_URL}/g/{data['id']}",
            pages_num=data["num_pages"],
            favourites=data["num_favorites"],
            tags=cls._parse_tags(data["tags"]),
        )

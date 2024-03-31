from __future__ import annotations

from .time import deltaconv as deltaconv

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Generator, Optional


def cutoff(
    text: str,
    limit: int = 2000,
    *,
    ending: str = "...",
) -> str:
    return (
        text if len(text) <= limit else (text[: limit - len(ending)]).strip() + ending
    )


def as_chunks(n: int, text: str) -> Generator[str, None, None]:
    for i in range(0, len(text), n):
        yield text[i : i + n]


def to_cb(text: str, lang: Optional[str]) -> str:
    return f"```{lang}\n{text}\n```"


del TYPE_CHECKING

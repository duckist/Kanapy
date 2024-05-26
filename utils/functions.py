from __future__ import annotations

import functools
import asyncio

from .time import deltaconv as deltaconv

from typing import TYPE_CHECKING, TypeVar, ParamSpec


R = TypeVar("R")
P = ParamSpec("P")

if TYPE_CHECKING:
    from typing import Generator, Awaitable, Callable, ParamSpec, TypeVar, Optional


def run_in_executor(
    _func: Callable[P, R],
) -> Callable[P, Awaitable[R]]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        func = functools.partial(_func, *args, **kwargs)
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(executor=None, func=func)

    return wrapped


def cutoff(
    text: str,
    limit: int = 2000,
    *,
    ending: str = "...",
) -> str:
    return (
        text if len(text) <= limit else (text[: limit - len(ending)]).strip() + ending
    )


def as_chunks(
    n: int,
    text: str,
) -> Generator[str, None, None]:
    for i in range(0, len(text), n):
        yield text[i : i + n]


def to_cb(
    text: str,
    lang: Optional[str],
) -> str:
    return f"```{lang}\n{text}\n```"

from .time import deltaconv as deltaconv


def cutoff(
    text: str,
    limit: int = 2000,
    *,
    ending: str = "...",
) -> str:
    return (
        text if len(text) <= limit else (text[: limit - len(ending)]).strip() + ending
    )

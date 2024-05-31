from __future__ import annotations

import re

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

QUERY_PATTERN = re.compile(r".* \(ID: ([0-9]+)\)")

TAG_PATTERN = re.compile(
    r"\<(?P<tag>[a-zA-Z]+)(?: href=\"(?P<url>.*)\")?\>(?:(?P<text>[\s\S]+?)\<\/\1\>)?",
    flags=re.M | re.S | re.U,
)


def formatter(match: re.Match[Any]) -> str:
    items = match.groupdict()

    match items["tag"]:
        case "a":
            return f"[{items['text']}]({items['url']})"
        case "br":
            return "\n"
        case "i":
            return f"*{items['text']}*"
        case "b":
            return f"**{items['text']}**"
        case _:
            return items["text"]


def cleanup_html(description: str) -> str:
    final, no = TAG_PATTERN.subn(formatter, description)
    if no > 0:
        return cleanup_html(final)

    return final.replace("\n\n", "\n")

from typing import Any, Dict

# random constants
FANCY_ARROW_RIGHT = "\U00002570"
BELL = "\U0001f514"
NO_BELL = "\U0001f515"
BOOK = "\U0001f4d6"
CAMERA = "\U0001f3a5"
ESCAPE = "\u001b"
INVIS_CHAR = "\u2800"
NL = "\n"

VALID_EDIT_KWARGS: Dict[str, Any] = {
    "content": None,
    "embed": None,
    "attachments": [],
    "delete_after": None,
    "allowed_mentions": None,
    "view": None,
}

NSFW_ERROR_MSG = (
    "The requested **%s** has been marked as NSFW. "
    "Switch to an NSFW channel or re-run the command in my DMs."
)


# emotes
WEBSOCKET = "<a:_:963608475982774282>"
CHAT_BOX = "<:_:963608317370974240>"
POSTGRES = "<:_:963608621017608294>"

YOUTUBE = "<:_:940649600920985691>"

DOUBLE_LEFT = "<:_:982445997269606450>"
LEFT = "<:_:982445470548893696>"
RIGHT = "<:_:982444215936118784>"
DOUBLE_RIGHT = "<:_:982379739165655060>"

# jank parsers
with open("schema.sql", "r") as f:
    STARTUP_QUERY = f.read()

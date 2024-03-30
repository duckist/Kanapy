import re
import discord

from typing import Any, List


class KanaMessage(discord.Message):
    async def edit(self, *args: Any, **kwargs: Any) -> discord.Message:
        embed = kwargs.get("embed")
        if embed and not embed.color:
            kwargs["embed"].color = 0xE59F9F

        for embed in kwargs.get("embeds", []):
            if not embed.color:
                embed.color = 0xE59F9F

        return await super().edit(*args, **kwargs)

    @property
    def custom_emojis(self) -> List[discord.PartialEmoji]:
        """
        Returns a list of all custom emojis in the message.

        Returns
        -------
        List[discord.PartialEmoji]
            A list of `PartialEmoji`s in the message.
        """
        emojis = re.findall(
            "<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>",
            self.content,
        )
        return [
            discord.PartialEmoji(animated=bool(animated), name=name, id=id)
            for animated, name, id in emojis
        ]


discord.state.Message = KanaMessage  # type: ignore
discord.message.Message = KanaMessage

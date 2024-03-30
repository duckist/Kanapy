from __future__ import annotations
from discord.ext import commands

import logging

from typing import TYPE_CHECKING

logger = logging.getLogger("discord")

if TYPE_CHECKING:
    from utils.subclasses import (
        Bot as Bot,
        Context as Context,
    )


class BaseCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

        self.CONFIG = bot.config["Cogs"].get(self.__cog_name__)
        if self.CONFIG and not self.CONFIG.get("ENABLED", True):
            raise Exception(
                f"{self.__cog_name__} is disabled. Please re-enable it or move it outside of the cog folder."
            )

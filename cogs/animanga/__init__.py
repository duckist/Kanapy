from .frontend import AnimangaFrontend
from .reminders import AnimangaReminders

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.subclasses import Bot


class Animanga(AnimangaFrontend): ...  # , AnimangaReminders


async def setup(bot: "Bot"):
    await bot.add_cog(Animanga(bot))

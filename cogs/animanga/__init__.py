from .frontend import Frontend
from .reminders import ReminderCog

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.subclasses import Bot


class AniManga(Frontend, ReminderCog): ...


async def setup(bot: "Bot"):
    await bot.add_cog(AniManga(bot))

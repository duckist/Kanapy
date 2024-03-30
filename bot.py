import tomllib
import discord

import utils.library_override # pyright: ignore[reportUnusedImport]
from utils.subclasses import Bot


with open("Config.toml", "rb") as f:
    config = tomllib.load(f)

bot = Bot(
    intents=discord.Intents().all(),
    case_insensitive=True,
    strip_after_prefix=True,
    config=config,
)

bot.run(
    config["Bot"]["TOKEN"],
)

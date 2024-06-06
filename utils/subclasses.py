import discord
from discord.ext import commands

import os
import glob
import toml

import asyncpg
import logging

from logging.handlers import QueueHandler
from asyncio import Queue, Lock
from aiohttp import ClientSession

from typing import Any, Dict, Type, Union

from utils import as_chunks, to_cb
from libs.anilist import AniList

from .constants import STARTUP_QUERY

queue: Queue[logging.LogRecord] = Queue()
log_handler = QueueHandler(queue)  # type: ignore

logger = logging.getLogger("discord")  # TODO: do logging properly
logger.addHandler(log_handler)


class Context(commands.Context["Bot"]):
    async def send(self, *args: Any, **kwargs: Any) -> discord.Message:
        embed = kwargs.get("embed")
        if embed and not embed.color:
            kwargs["embed"].color = int(self.bot.config["Bot"]["DEFAULT_COLOR"], 16)

        for embed in kwargs.get("embeds", []):
            if not embed.color:
                embed.color = int(self.bot.config["Bot"]["DEFAULT_COLOR"], 16)

        return await super().send(*args, **kwargs)

    async def reply(self, *args: Any, **kwargs: Any) -> discord.Message:
        if not kwargs.get("mention_author"):
            kwargs["mention_author"] = False

        return await super().reply(*args, **kwargs)


async def get_prefix(bot: "Bot", message: discord.Message):
    if not message.guild:
        pref = bot.config["Bot"]["DEFAULT_PREFIX"]
        return commands.when_mentioned_or(pref)(bot, message)

    q = bot.prefixes.get(message.guild.id, None)
    if q:
        return commands.when_mentioned_or(q)(bot, message)

    pref = bot.config["Bot"]["DEFAULT_PREFIX"]

    await bot.pool.execute(
        """
    INSERT INTO guild_settings
        VALUES ($1, $2);
    """,
        message.guild.id,
        pref,
    )
    bot.prefixes[message.guild.id] = pref

    return commands.when_mentioned_or(pref)(bot, message)


class Bot(commands.Bot):
    queue: Queue[logging.LogRecord]
    anilist: AniList

    def __init__(self, *args: Any, **kwargs: Any):
        kwargs.setdefault("command_prefix", get_prefix)
        super().__init__(*args, **kwargs)

        self.config = kwargs["config"]
        self.config_lock = Lock()

    async def dump_config(self):
        async with self.config_lock:
            with open("Config.toml") as f:
                toml.dump(self.config, f)

        logging.info("dumped config.")

    async def get_context(
        self,
        message: Union[discord.Message, discord.Interaction],
        *,
        cls: Type[commands.Context["Bot"]] = Context,
    ):
        return await super().get_context(message, cls=cls)

    async def on_bot_ready(self) -> None:
        await self.wait_until_ready()
        logger.info(f"{self.user} is online, on discord.py - {discord.__version__}")

        # Set guild, this is crucial to other components of the bot.
        GUILD_ID = self.config["Bot"]["GUILD_ID"]
        if not GUILD_ID:
            logger.info("No GUILD_ID set, creating a guild.")
            self.guild = await self.create_guild(name=self.config["Bot"]["GUILD_NAME"])
            self.config["Bot"]["GUILD_ID"] = self.guild.id
            await self.dump_config()
        else:
            self.guild = self.get_guild(GUILD_ID) or await self.fetch_guild(GUILD_ID)

    async def send_output(self):
        def avatar(avatar_id: int) -> str:
            return f"https://cdn.discordapp.com/embed/avatars/{avatar_id}.png"

        # fmt: off
        # Mapping of ERROR_NO: (USERNAME, AVATAR)
        ERROR_TYPE_MAPPING = {
            50: ("CRITICAL", avatar(4)), # red
            40: ("ERROR",    avatar(4)), # red
            30: ("WARNING",  avatar(3)), # yellow
            20: ("INFO",     avatar(1)), # grey
            10: ("DEBUG",    avatar(1)), # grey
             0: ("NOTSET",   avatar(1)), # grey
        }
        # fmt: on

        while True:
            log: logging.LogRecord = await queue.get()
            name, avatar_url = ERROR_TYPE_MAPPING[log.levelno]
            message = log.getMessage()

            if log.levelno >= 40:
                for chunk in as_chunks(3990, message):
                    embed = discord.Embed(
                        description=to_cb(chunk, "py"), color=0xFF0000
                    )

                    await self.stdout_webhook.send(
                        embed=embed, username=name, avatar_url=avatar_url
                    )
            else:
                for chunk in as_chunks(2000, message):
                    await self.stdout_webhook.send(
                        username=name,
                        avatar_url=avatar_url,
                        content=chunk,
                    )

    async def setup_hook(self):
        # called before the bot starts
        self.session = ClientSession()
        self.anilist = AniList(
            self.session,
            anilist_id=self.config["Bot"]["ANILIST_ID"],
            anilist_secret=self.config["Bot"]["ANILIST_SECRET"],
        )
        self.start_time = discord.utils.utcnow()
        self.is_dev = self.config["Bot"]["IS_DEV"]

        self.loop.create_task(self.on_bot_ready())

        # to redirect the errors to a webhook or not.
        output = self.config["Bot"]["Output"]
        if output["SEND_TO_WEBHOOK"]:
            if output["WEBHOOK"]:
                self.stdout_webhook = discord.Webhook.from_url(
                    output["WEBHOOK"], session=ClientSession()
                )  # tying it to a different session just incase
            else:
                logger.info("No webhook set, creating a channel along with a webhook.")
                channel = await self.guild.create_text_channel(name="stdout")

                self.stdout_webhook = await channel.create_webhook(name="logger")
                output["WEBHOOK"] = self.stdout_webhook.url
                await self.dump_config()

            self.loop.create_task(self.send_output())

        conn = await asyncpg.create_pool(
            self.config["Bot"]["PSQL_URI"],
            min_size=1,
            max_size=5,  # TODO: remove this
        )
        if conn is None:
            raise RuntimeError("Could not connect to the DATABASE")

        self.pool = conn

        await self.pool.execute(STARTUP_QUERY)

        self.prefixes: Dict[int, str] = {
            prefix["guild_id"]: prefix["prefix"]
            for prefix in (
                await self.pool.fetch("SELECT guild_id, prefix FROM guild_settings;")
            )
        }

        self.disabled_modules: Dict[int, str] = {
            module["guild_id"]: module["disabled_modules"]
            for module in (
                await self.pool.fetch(
                    "SELECT guild_id, disabled_modules FROM guild_settings"
                )
            )
            if module["disabled_modules"] is not None
        }

        jishaku = self.config["Jishaku"]
        if jishaku["ENABLED"]:
            await self.load_extension("jishaku")

            for config, enabled in jishaku.pop("Settings").items():
                os.environ[f"JISHAKU_{config}"] = str(
                    enabled
                )  # because it doesn't like a bool.

        for cog in glob.glob("cogs/[!_]*"):
            cog = cog.replace("\\", ".").replace("/", ".").removesuffix(".py")

            try:
                await self.load_extension(cog)
            except Exception as _error:
                logger.exception(f"Failed to load {cog}, due to:")
            else:
                logger.info(f"Loaded {cog}")

    def run(self, *args: Any, **kwargs: Any):
        super().run(*args, **kwargs)

    async def close(self):
        await super().close()
        await self.pool.close()
        await self.session.close()

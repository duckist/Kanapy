import discord
from discord.ext import commands


from . import BaseCog

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from utils.subclasses import Bot, Context


class Moderation(BaseCog):
    def __init__(self, bot: "Bot"):
        super().__init__(bot)
        self.bot = bot
        self.modules = {
            "snipe": "Lets users 'snipe' the last message that got deleted/edited within the last 2 minutes in a channel.",
        }

    @commands.command(aliases=["bp", "purgebots", "purgebot"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def botpurge(
        self,
        ctx: "Context",
        bot: discord.Member,
        prefix: str,
        amount: commands.Range[int, 30, 100],
    ):
        """
        Purges a set of bot commands along with their invokee commands.

        Parameters
        -----------
        bot: discord.Member
            The bot to purge
        prefix: str
            The prefix of the bot to purge
        amount: int
            The amount of posts to purge, must be under 100.
        """

        if isinstance(
            ctx.channel,
            discord.DMChannel | discord.PartialMessageable | discord.GroupChannel,
        ):  # purely for linter
            return

        if amount > 100:
            return await ctx.reply("Please enter a smaller number")

        results: dict[str, int] = {}

        def check(message: discord.Message):
            if message.author.id == bot.id or message.content.startswith(prefix):
                if not results.get(message.author.name):
                    results[message.author.name] = 1
                else:
                    results[message.author.name] += 1
                return True
            return False

        await ctx.channel.purge(limit=amount, check=check)
        await ctx.send(
            embed=discord.Embed(
                title="Purge Results",
                description="\n".join(f"{k} - {v}" for k, v in results.items()),
            ),
            delete_after=10,
        )

    @commands.command(aliases=["wp", "mp", "mudaepurge"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def waifupurge(self, ctx: "Context", amount: int = 30):
        """
        Purges a set of Mudae bot's spam along with the commands.

        Parameters
        -----------
        amount: int
            The amount of posts to purge.
        """
        await ctx.invoke(
            self.botpurge,
            discord.Object(id=432610292342587392),  # type: ignore
            "$",
            amount,
        )

    @commands.command()
    @commands.guild_only()
    async def prefix(self, ctx: "Context", prefix: Optional[str]):
        """
        Changes the guild specific prefix. if no prefix is given, it will show the current prefix.

        Parameters
        -----------
        prefix: Optional[str]
            The prefix to change.
        """

        assert ctx.guild and isinstance(ctx.author, discord.Member)

        if prefix is None:
            return await ctx.send(
                f"The current prefix for this server is: `{self.bot.prefixes.get(ctx.guild.id, 'uwu')}`"
            )

        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(["administrator"])

        await self.bot.pool.execute(
            """
        UPDATE guild_settings
        SET prefix = $1
        WHERE guild_id = $2;
        """,
            prefix,
            ctx.guild.id,
        )
        self.bot.prefixes[ctx.guild.id] = prefix

        await ctx.send(f"The prefix is now `{prefix}`")

    @commands.group(
        aliases=["config", "configs", "modules"], invoke_without_command=True
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def module(self, ctx: "Context"):
        """
        Configure modules.
        """
        await ctx.send_help(ctx.command)

    @module.command(name="list", aliases=["all"])
    @commands.has_permissions(manage_guild=True)
    async def _list(self, ctx: "Context"):
        """
        Lists all modules and their current status in the server.
        """
        if not ctx.guild:
            return

        WHITE_CHECK_MARK = "\u2705"
        CROSS_EMOJI = "\u274c"

        desc = ""
        for module, description in self.modules.items():
            desc += f"\n{WHITE_CHECK_MARK if module not in self.bot.disabled_modules.get(ctx.guild.id, ['']) else CROSS_EMOJI} {module}: {description}"

        embed = discord.Embed(title="Modules", description=desc)
        await ctx.send(embed=embed)

    @module.command(aliases=["on"])
    @commands.has_permissions(manage_guild=True)
    async def enable(self, ctx: "Context", module: str):
        """
        Enables a module in the server.

        Parameters
        -----------
        module: str
            The name of the module to disable.
        """
        if not ctx.guild:
            return

        module = module.lower()
        if module not in self.modules:
            return await ctx.send(f"Module `{module}` does not exist.")

        if module not in self.bot.disabled_modules.get(ctx.guild.id, [""]):
            return await ctx.send(f"Module `{module}` is already enabled.")

        q = """
        UPDATE guild_settings
            SET disabled_modules = ARRAY_REMOVE(disabled_modules, $1)
                WHERE guild_id = $2
        RETURNING disabled_modules;
        """
        disabled_modules = await self.bot.pool.fetchval(q, module, ctx.guild.id)
        self.bot.disabled_modules[ctx.guild.id] = disabled_modules
        await ctx.send(f"Module `{module}` has been enabled.")

    @module.command(aliases=["off"])
    @commands.has_permissions(manage_guild=True)
    async def disable(self, ctx: "Context", module: str):
        """
        Disables a module in the server.

        Parameters
        -----------
        module: str
            The name of the module to disable.
        """
        if not ctx.guild:
            return

        module = module.lower()
        if module not in self.modules:
            return await ctx.send(f"Module `{module}` does not exist.")

        if module in self.bot.disabled_modules.get(ctx.guild.id, [""]):
            return await ctx.send(f"Module `{module}` is already disabled.")

        q = """
        UPDATE guild_settings
            SET disabled_modules = ARRAY_APPEND(disabled_modules, $1)
                WHERE guild_id = $2
        RETURNING disabled_modules;
        """
        disabled_modules = await self.bot.pool.fetchval(q, module, ctx.guild.id)
        self.bot.disabled_modules[ctx.guild.id] = disabled_modules
        await ctx.send(f"Module `{module}` has been disabled.")


async def setup(bot: "Bot"):
    await bot.add_cog(Moderation(bot))

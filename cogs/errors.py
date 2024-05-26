from discord.ext import commands

from jishaku.features.root_command import natural_size as ns  # pyright: ignore[reportPrivateImportUsage]

from utils import deltaconv
from utils.constants import NSFW_ERROR_MSG

from . import BaseCog
from .download import FileTooLarge

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.subclasses import Bot, Context


def format_errors(perms: list[str]) -> str:
    missing = [
        perm.replace("_", " ").replace("guild", "server").title() for perm in perms
    ]

    if len(missing) > 2:
        return "{}, and {}".format("**, **".join(missing[:-1]), missing[-1])

    return " and ".join(missing)


class Errors(BaseCog):
    @commands.Cog.listener()
    async def on_command_error(self, ctx: "Context", error: commands.CommandError):
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.BotMissingPermissions):
            fmt = format_errors(error.missing_permissions)
            return await ctx.reply(
                f"I need the `{fmt}` permissions to run this command."
            )

        if isinstance(error, commands.MissingPermissions):
            fmt = format_errors(error.missing_permissions)
            return await ctx.reply(
                f"You need the `{fmt}` permissions to use this command."
            )

        if isinstance(error, commands.NSFWChannelRequired):
            return await ctx.send(NSFW_ERROR_MSG % "command")

        if isinstance(error, commands.CheckFailure):
            return await ctx.reply("You do not have permission to use this command.")

        if isinstance(error, commands.errors.ChannelNotFound):
            return await ctx.reply(f"`{error.argument}` is not a valid channel.")

        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.reply(f"You're missing the `{error.param.name}` argument.")

        if isinstance(error, commands.errors.CommandOnCooldown):
            formatted_time = deltaconv(round(error.retry_after))
            return await ctx.reply(
                f"You're under cooldown for `{formatted_time}`.",
                delete_after=error.retry_after,
            )

        if isinstance(error, commands.BadArgument):
            return await ctx.reply(
                error.args[0]
            )  # these errors are usually raised by me, so i can do this.

        if isinstance(error, FileTooLarge):
            return await error.original_message.edit(
                content=f"Sorry, the file is too large to upload. I can only send `{ns(error.limit)}` worth of files here."
            )

        await ctx.send("Something went wrong. This incident has been reported.")
        raise error


async def setup(bot: "Bot"):
    await bot.add_cog(Errors(bot))

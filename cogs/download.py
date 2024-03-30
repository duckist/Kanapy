import random
import discord
from discord.ext import commands

import re
import asyncio

import yt_dlp  # pyright: ignore[reportMissingTypeStubs]

# fmt: off
from yt_dlp.extractor.youtube import YoutubeIE, YoutubeClipIE  # pyright: ignore[reportMissingTypeStubs]
from yt_dlp.extractor.pinterest import PinterestIE             # pyright: ignore[reportMissingTypeStubs]
from yt_dlp.extractor.twitter import TwitterIE                 # pyright: ignore[reportMissingTypeStubs]
from yt_dlp.extractor.instagram import InstagramIE             # pyright: ignore[reportMissingTypeStubs]
from yt_dlp.extractor.tiktok import TikTokIE                   # pyright: ignore[reportMissingTypeStubs]
from yt_dlp.extractor.reddit import RedditIE                   # pyright: ignore[reportMissingTypeStubs]
from yt_dlp.extractor.twitch import TwitchClipsIE              # pyright: ignore[reportMissingTypeStubs]
# fmt: on

from pathlib import Path
from time import perf_counter

from . import BaseCog

from typing import TYPE_CHECKING, Any, Literal, Optional, Annotated, TypedDict

if TYPE_CHECKING:
    from utils.subclasses import Bot, Context

DEFAULT_UPLOAD_LIMIT = 25 * 1024 * 1024


class Match(TypedDict):
    url: str
    source: str


class Source:
    def __init__(self, sources: dict[str, str] = {}):
        # All the flags from the regexes would be put in this set,
        # then is going to be added on to the `final_re`.
        self._flags: set[str] = set()

        self.sources = {k: self.cleanse_re(v) for k, v in sources.items()}
        self.final_regex = self.construct_re()

    def _fmt_name(self, name: str) -> str:
        return f"`{name.replace('_', ' ').title()}`"

    def source_names(self):
        sources = list(self.sources.keys())

        if len(sources) > 1:
            return (
                ", ".join(self._fmt_name(k) for k in sources[:-1])
                + f" or {self._fmt_name(sources[-1])}"
            )
        else:
            return self._fmt_name(sources[0])

    def construct_re(self):
        return (
            rf"(?{''.join(self._flags)})^"
            rf"({ '|'.join(f'(?P<{k}>{v})' for k, v in self.sources.items()) })"
        )

    def __remove_flag(self, match: re.Match[str]) -> str:
        data = match.groupdict()
        self._flags.update(set(data["flags"]))
        return ""

    def cleanse_re(self, regex: str) -> str:
        regex = re.sub(
            r"\?P\<\w+\>",  # remove IDs
            "",
            regex.replace("/", r"\/"),
        )

        # take away the regex flags and put it in a set, to output it at the end of the final regex.
        regex = re.sub(
            r"\(\?(?P<flags>[a-z]+)\)\^?",
            self.__remove_flag,
            regex,
        )

        return regex

    def match(self, other: str) -> Optional[Match]:
        if other.startswith("<"):
            other = other[1:]

        if other.endswith(">"):
            other = other[:-1]

        if match := re.match(self.final_regex, other):
            for (
                k,
                v,
            ) in (
                match.groupdict().items()
            ):  # bit jank, but don't have a work around for now.
                if v:
                    return {"url": match.groups()[0], "source": k}


# fmt: off
sources = Source({
    "youtube":       YoutubeIE._VALID_URL,     # pyright: ignore[reportPrivateUsage]
    "youtube_clips": YoutubeClipIE._VALID_URL, # pyright: ignore[reportPrivateUsage]
    "twitter":       TwitterIE._VALID_URL,     # pyright: ignore[reportPrivateUsage]
    "pinterest":     PinterestIE._VALID_URL,   # pyright: ignore[reportPrivateUsage]
    "tiktok":        TikTokIE._VALID_URL,      # pyright: ignore[reportPrivateUsage]
    "instagram":     InstagramIE._VALID_URL,   # pyright: ignore[reportPrivateUsage]
    "reddit":        RedditIE._VALID_URL,      # pyright: ignore[reportPrivateUsage]
    "twitch_clips":  TwitchClipsIE._VALID_URL, # pyright: ignore[reportPrivateUsage]
})
# fmt: on


class FileTooLarge(Exception):
    def __init__(self, limit: int, message: discord.Message, *args: object) -> None:
        super().__init__(*args)
        self.limit = limit
        self.original_message = message


class LinkConverter(commands.Converter["Bot"]):
    async def convert(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, ctx: "Context", argument: str
    ):
        match = sources.match(argument)
        if match:
            return match
        elif "-dev" in ctx.message.content and await ctx.bot.is_owner(ctx.author):
            return {"source": "unknown", "url": argument}
        else:
            raise commands.BadArgument(
                f"No URL found, sources I support are {sources.source_names()}."
            )


class DownloadCommandFlags(commands.FlagConverter, delimiter=" ", prefix="-"):
    fmt: Literal["mp4", "mp3", "webm"] = commands.flag(
        description="Video format the downloaded video should be downloaded as.",
        default="mp4",
        aliases=["format", "f"],
    )
    spoiler: bool = commands.flag(
        description="Spoilers the sent video.", default=False, aliases=["s", "sp"]
    )
    dev: bool = commands.flag(default=False)


class Download(BaseCog):
    def __init__(self, bot: "Bot") -> None:
        super().__init__(bot)
        self.DOWNLOAD_PATH = self.CONFIG["PATH_TO_DOWNLOAD"]

    def _download(
        self,
        data: Match,
        flags: DownloadCommandFlags,
        *,
        max_filesize: int = DEFAULT_UPLOAD_LIMIT,
    ) -> Optional[Path]:
        _id = random.randint(0, 1000)
        isAudio = flags.fmt in ("mp3",)

        options = {
            "outtmpl": self.DOWNLOAD_PATH + f"{_id}_%(id)s.%(ext)s",
            "quiet": not self.bot.config["Bot"]["IS_DEV"],
            "merge_output_format": flags.fmt,
            "max_filesize": max_filesize,
        }

        if data["source"] == "tiktok":
            options["format_sort"] = ["vcodec:h264"]

        if data["source"] == "twitter":
            options["cookies"] = "cookies.txt"

            # because of a bug with yt_dlp, the `filename` would be different
            # but the `%(filename)q` template string won't update, and would
            # have a different file extension.
            if not isAudio:
                options["postprocessors"] = [
                    {
                        "key": "Exec",
                        "exec_cmd": [
                            "mv %(filename)q %(filename)q.temp",
                            "ffmpeg -y -i %(filename)q.temp -c copy -map 0 -brand mp42 %(filename)q",
                            "rm %(filename)q.temp",
                        ],
                        "when": "after_move",
                    }
                ]

        if isAudio:
            options["format"] = "bestaudio/best"
            options.setdefault("postprocessors", []).append(  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue]  # screw u pyright let me golf in peace
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": flags.fmt,
                    "preferredquality": "192",
                }
            )
        else:
            options["format"] = f"bestvideo+bestaudio[ext={flags.fmt}]/best"

        with yt_dlp.YoutubeDL(  # pyright: ignore[reportUnknownMemberType]
            options
        ) as ydl:
            info: dict[str, Any] = ydl.extract_info(data["url"])  # pyright: ignore

        path = Path(
            f"{self.DOWNLOAD_PATH}{_id}_{info['id']}.{flags.fmt if isAudio else info['ext']}"
        )
        if path.exists():
            if path.stat().st_size < max_filesize:
                return path

            path.unlink(missing_ok=True)

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command()
    @commands.bot_has_permissions(attach_files=True)
    async def download(
        self,
        ctx: "Context",
        url: Annotated[Match, LinkConverter],
        *,
        flags: DownloadCommandFlags,
    ):
        """
        Downloads the provided video and send it to the current channel,
        Allowed sources are `YouTube`, `Reddit`, `TikTok`, `Twitter`, `Pinterest`, `Twitch` or `Instagram`.

        Parameters
        -----------
        url: str
            The video to download.
        """
        msg = await ctx.send("downloading...")
        limit = ctx.guild.filesize_limit if ctx.guild else DEFAULT_UPLOAD_LIMIT

        try:
            start = perf_counter()
            path = await asyncio.to_thread(
                self._download, url, flags, max_filesize=limit
            )
            end = perf_counter()
        except yt_dlp.utils.DownloadError:  # pyright: ignore[reportUnknownMemberType]
            return await msg.edit(
                content="Could not download the URL. Double check the URL and try again."
            )

        if not path:
            raise FileTooLarge(
                limit, msg
            )  # if its not found, its safe to assume it's errored because of the file limit.

        try:
            await msg.edit(
                content=f"took: `{round(end - start, 2)}s`",
                attachments=[discord.File(path, spoiler=flags.spoiler)],
            )
        except discord.HTTPException as err:
            if (
                err.code == 40005
            ):  # if discord somehow still doesn't like my 25MB files, i'd like to let the user know.
                raise FileTooLarge(limit, msg)

            raise err
        finally:
            path.unlink(missing_ok=True)  # boop


async def setup(bot: "Bot"):
    await bot.add_cog(Download(bot))

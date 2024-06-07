from __future__ import annotations

import re

import discord
from discord import ui
from discord.ext import commands

from urllib.parse import quote

from utils.constants import BELL, BOOK, CAMERA, NO_BELL
from libs.anilist.types import Media, Relation, SearchType

from typing import TYPE_CHECKING, Optional, Self, Any

if TYPE_CHECKING:
    from . import Animanga
    from utils.subclasses import Bot


def is_nsfw(
    ctx: commands.Context[Bot],
    media: Media,
) -> bool:
    if media.is_adult and not (
        isinstance(
            ctx.channel,
            discord.DMChannel | discord.PartialMessageable | discord.GroupChannel,
        )
        or ctx.channel.is_nsfw()
    ):
        return True

    return False


class MediaView(ui.View):
    @classmethod
    async def from_data(
        cls,
        media: Media,
        bot: Bot,
        user_id: Optional[int] = None,
    ) -> Self | discord.utils.MISSING:
        view = discord.utils.MISSING
        if media.relations:
            view = view or cls(timeout=None)
            view.add_item(RelationSelect(media.relations))

        if media.trailer:
            view = view or cls(timeout=None)
            view.add_item(
                ui.Button(
                    label="Trailer",
                    url=media.trailer.strip(),
                    row=2,
                )
            )

        if media.next_airing_episode and user_id:
            view = view or cls(timeout=None)
            view.add_item(
                await ReminderButton.for_user(
                    bot,
                    media.id,
                    user_id,
                )
            )

        return view


class RelationSelect(
    ui.DynamicItem[ui.Select[MediaView]],
    template=r"kana:animanga_relations",
):
    def __init__(self, relations: list[Relation]) -> None:
        super().__init__(
            ui.Select[MediaView](
                placeholder="Related",
                custom_id="kana:animanga_relations",
                options=self._to_options(relations),
                row=1,
            ),
        )

    def _to_options(self, relations: list[Relation]) -> list[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=relation.title,
                description=relation.relation_type.replace("_", " ").title(),
                emoji=BOOK if relation.type == "MANGA" else CAMERA,
                value=f"{relation.type}_{relation.id}",
                default=False,
            )
            for relation in relations
        ][:25]

    async def _query_anilist(
        self,
        interaction: discord.Interaction["Bot"],
        search_id: str,
        search_type: str,
        *,
        attempt: int = 0,
    ) -> Optional[Media]:
        media = await interaction.client.anilist.fetch(
            f"x (ID: {search_id})",  # bit jank but who is gonna stop me
            search_type=SearchType.ANIME
            if search_type == "ANIME"
            else SearchType.MANGA,
        )

        if not media and attempt < 3:
            return await self._query_anilist(
                interaction, search_id, search_type, attempt=attempt
            )

        return media

    @classmethod
    async def from_custom_id(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        _interaction: discord.Interaction[Bot],
        _item: ui.Select[MediaView],
        _match: re.Match[str],
    ) -> Self:
        return cls([])

    async def callback(self, interaction: discord.Interaction["Bot"]):  # type: ignore
        await interaction.response.defer(ephemeral=True)
        search_type, search_id = self.item.values[0].split("_")

        media = await self._query_anilist(interaction, search_id, search_type)

        if not media:
            return await interaction.edit_original_response(view=self.view)

        view = await MediaView.from_data(
            media,
            interaction.client,
            interaction.user.id,
        )

        await interaction.followup.send(
            embed=MediaEmbed.from_data(media),
            ephemeral=True,
            view=view,  # pyright: ignore[reportArgumentType]
        )


class ReminderButton(
    ui.DynamicItem[ui.Button[ui.View]],
    template=r"kana:r_(?P<anime_id>\d+)_(?P<user_id>\d+)",
):
    def __init__(
        self,
        is_active: bool,
        anime_id: int,
        user_id: int,
    ):
        super().__init__(
            ui.Button[ui.View](
                emoji=BELL if is_active else NO_BELL,
                style=discord.ButtonStyle.green
                if is_active
                else discord.ButtonStyle.gray,
                custom_id=f"kana:r_{anime_id}_{user_id}",
                row=2,
            ),
        )

        self.anime_id = anime_id
        self.user_id = user_id

    @classmethod
    async def for_user(
        cls,
        bot: Bot,
        anime_id: int,
        user_id: int,
    ) -> Self:
        is_active = await bot.pool.fetchval(
            """
            SELECT TRUE FROM anime_reminders
                WHERE anilist_id = $1
                  AND user_id = $2
            """,
            anime_id,
            user_id,
        )

        return cls(is_active, anime_id, user_id)

    async def toggle_reminder(
        self,
        bot: Bot,
        anime_id: int,
        user_id: int,
    ) -> bool:
        reminder: Optional[Animanga] = bot.get_cog("Animanga")  # pyright: ignore[reportAssignmentType]
        if not reminder:
            raise ValueError("Animanga cog not loaded")

        toggle = await reminder.toggle_reminder_for(user_id, anime_id)
        return toggle

    @classmethod
    async def from_custom_id(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        interaction: discord.Interaction[Bot],
        _: ui.Button[ui.View],
        match: re.Match[str],
    ) -> Self:
        anime_id, user_id = int(match["anime_id"]), int(match["user_id"])
        is_active = await interaction.client.pool.fetchval(
            """
            SELECT TRUE FROM anime_reminders
                WHERE anilist_id = $1
                  AND user_id = $2
            """,
            anime_id,
            user_id,
        )

        return cls(is_active, anime_id, user_id)

    async def callback(self, interaction: discord.Interaction[Bot]):  # pyright: ignore[reportIncompatibleMethodOverride]
        assert self.view

        is_toggled = await self.toggle_reminder(
            interaction.client,
            self.anime_id,
            interaction.user.id,
        )

        if self.user_id == interaction.user.id:
            self.item.style = (
                discord.ButtonStyle.green if is_toggled else discord.ButtonStyle.gray
            )
            self.item.emoji = BELL if is_toggled else NO_BELL

            await interaction.response.edit_message(view=self.view)

        args = {
            "content": "Got it! I'll remind you when an episode of this anime is released."
            if is_toggled
            else "Removing reminders for this anime.",
            "ephemeral": True,
        }

        if interaction.response.is_done():
            await interaction.followup.send(**args)  # type: ignore
        else:
            await interaction.response.send_message(**args)  # type: ignore


class MediaEmbed(discord.Embed):
    @classmethod
    def from_data(cls, data: Media) -> Self:
        embed = cls(
            title=data.title,
            description=data.description,
            color=discord.Color.from_str(data.color) if data.color else 0xE6E6E6,
            url=data.site_url,
        )

        embed.set_thumbnail(url=data.cover_image)
        embed.set_image(url=data.banner_image)

        embed.add_field(
            name="Genres",
            value=", ".join(
                f"[{genre}](https://anilist.co/search/{data.type.name.lower()}?genres={quote(genre)})"
                for genre in data.genres
            ),
        )

        embed.add_field(
            name="Score",
            value=f"{data.average_score}/100" if data.average_score else "NaN",
        )
        embed.add_field(name="Status", value=data.status)

        if data.episodes:
            embed.add_field(name="Episodes", value=data.episodes)

        if data.chapters:
            embed.add_field(name="Chapters", value=data.chapters)

        if data.studios:
            embed.add_field(name="Studio", value=data.studios[0].formatted)

        return embed


class AniListUserConverter(commands.Converter["Bot"]):
    async def convert(self, ctx: commands.Context[Bot], arg: str):  # pyright: ignore[reportIncompatibleMethodOverride]
        try:
            member = await commands.UserConverter().convert(ctx, arg)

            access_token = await ctx.bot.pool.fetchval(
                "SELECT access_token FROM anilist_tokens WHERE user_id = $1",
                member.id,
            )

            if not access_token:
                raise commands.BadArgument(
                    f"You don't have an AniList account linked. You can link your AniList account with `{ctx.clean_prefix} anilist login`."
                    if ctx.author.id == member.id
                    else f"**{member.display_name}** does not have an AniList account linked."
                )

            try:
                user_id = await ctx.bot.anilist.fetch_user_id(access_token)
            except Exception:
                await ctx.bot.pool.execute(
                    "DELETE FROM anilist_tokens WHERE user_id = $1",
                    member.id,
                )

                raise commands.BadArgument(
                    f"Your AniList account token has expired, please login again with `{ctx.clean_prefix} anilist login`."
                    if ctx.author.id == member.id
                    else f"**{member.display_name}**'s AniList account token has expired."
                )

            return user_id
        except Exception as e:
            if isinstance(e, commands.BadArgument):
                raise e

            try:
                user = await ctx.bot.anilist.get_user_id(
                    int(arg) if arg.isdigit() else arg,
                )
            except Exception:
                raise commands.BadArgument(f"User `{arg}` not found on AniList.")

            return user


class LoginModal(ui.Modal, title="AniList Login"):
    code = ui.TextInput[Self](
        label="Access Code",
        placeholder="Enter your code",
        style=discord.TextStyle.short,
    )

    def __init__(self, bot: Bot, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not self.code.value or self.code.value == "undefined":
            raise ValueError

        try:
            token = await self.bot.anilist.get_access_token(self.code.value)
        except Exception:
            raise ValueError from Exception

        await self.bot.pool.execute(
            """
            INSERT INTO anilist_tokens
                (user_id, access_token, expires_in)
            VALUES
                ($1, $2, $3)
            ON CONFLICT 
                (user_id)
            DO UPDATE SET
                access_token = $2,
                expires_in = $3
            """,
            interaction.user.id,
            token.access_token,
            token.expiry,
        )

        await interaction.response.send_message(
            "Successfully logged in!",
            ephemeral=True,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        if isinstance(error, ValueError):
            return await interaction.response.send_message(
                "Invalid code. Please try again.",
                ephemeral=True,
            )

        return await super().on_error(interaction, error)


class LoginView(ui.View):
    def __init__(self, bot: Bot):
        super().__init__(timeout=None)
        self.add_item(
            ui.Button(
                url=f"https://anilist.co/api/v2/oauth/authorize?client_id={bot.anilist.ANILIST_ID}&redirect_uri=https://anilist.co/api/v2/oauth/pin&response_type=code",
                label="Get Code",
            ),
        )

    @ui.button(label="Submit Code", style=discord.ButtonStyle.green)
    async def _login(
        self,
        interaction: discord.Interaction[Bot],
        _: ui.Button[Self],
    ):
        await interaction.response.send_modal(
            LoginModal(interaction.client),
        )

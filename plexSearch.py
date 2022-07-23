import datetime

import discord
import plexapi.video
from discord.ext import commands
from discord.ext.commands import command
from discord_components import DiscordComponents, Button, ButtonStyle, SelectOption, Select, Interaction


class PlexSearch(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def stringify(self, genres: []):
        """Convert a list of genres to a string"""
        str_genres = []
        for genre in genres:
            str_genres.append(genre.tag)
        return ", ".join(str_genres)

    def rating_formatter(self, rating):
        if rating is None:
            return "N/A"
        else:
            return f"{round(rating * 10)}%"


    @command(name="content_search", aliases=["cs"])
    async def search(self, ctx, *, query):
        """
        Searches Plex for a specific content.
        """
        plex = ctx.plex
        results = plex.search(query)

        # Remove anything that doesn't have a plexapi.video.Video base class
        results = [r for r in results if isinstance(r, plexapi.video.Video)]

        if not results:
            await ctx.send("No results found.")
            return
        elif len(results) == 1:
            msg = await ctx.send("Found 1 result. Showing details...")
            await self.content_details(msg, results[0], ctx.author)
            return
        else:
            select_thing = Select(
                custom_id=f"content_search_{ctx.message.id}",
                options=[
                    SelectOption(
                        label=f"{result.title} ({result.year})",
                        value=f"{result.title}_{hash(result)}",
                        default=False,
                    ) for result in results
                ],
            )
            self.bot.component_manager.add_callback(select_thing, self.on_select)
            embed = discord.Embed(title="Search results for '%s'" % query, color=0x00ff00)
            for result in results:
                embed.add_field(name=f"{result.title} ({result.year})", value=result.summary, inline=False)
            cancel_button = Button(
                label="Cancel",
                style=ButtonStyle.red,
                custom_id=f"cancel_{ctx.message.id}",
            )

            self.bot.component_manager.add_callback(cancel_button, self.on_select)
            await ctx.send(embed=embed, components=[select_thing, cancel_button])

        # Clear all components

    async def on_select(self, inter: Interaction):
        if inter.custom_id.startswith("cancel"):
            await inter.disable_components()
            return
        if inter.custom_id.startswith("content_search"):
            # Get the selected result
            plex = await self.bot.fetch_plex(inter.guild)
            library = plex.library
            if inter.values[0].startswith("season"):
                # Season
                season_id = inter.values[0].split("_")[1]
                season = library.getGuid(season_id)
                await self.content_details(inter.message, season, inter.author, inter)
            elif inter.values[0].startswith("episode"):
                # Episode
                episode_id = inter.values[0].split("_")[1]
                episode = library.getGuid(episode_id)
                await self.content_details(inter.message, episode, inter.author, inter)
            else:
                # Run plex search
                result = plex.search(inter.values[0].split('_')[0])[0]
                await self.content_details(inter.message, result, inter.author, inter)

    async def content_details(self, edit_msg, content, requester, inter: Interaction = None):
        """"""

        if hasattr(content, 'audienceRating') and hasattr(content, 'rating'):
            rating_string = f"`{content.contentRating}` | " \
                            f"Audience `{self.rating_formatter(content.audienceRating )}`" \
                            f" | Critics `{self.rating_formatter(content.rating)}`"
        else:
            rating_string = "No ratings available"

        media_info = []
        embed = discord.Embed(title="Media type not implemented", color=0x00ff00)
        select_thing = None

        if hasattr(content, 'media'):
            index = 1
            for media in content.media:
                media_info.append(f"File#`{index}`: `{media.container}` - `{media.videoCodec}:"
                                  f" {media.width}x{media.height}@{media.videoFrameRate} "
                                  f"| {media.audioCodec}: {media.audioChannels}ch`")
                index += 1

        if isinstance(content, plexapi.video.Movie):
            """Format the embed being sent for a movie"""
            embed = discord.Embed(title=f"{content.title} ({content.year})",
                                  description=f"{content.tagline}", color=0x00ff00)
            embed.add_field(name="Summary", value=content.summary, inline=False)
            embed.add_field(name="Ratings", value=rating_string, inline=False)
            embed.add_field(name="Genres", value=self.stringify(content.genres), inline=True)
            embed.add_field(name="Directors", value=self.stringify(content.directors), inline=True)
            embed.add_field(name="Writers", value=self.stringify(content.writers), inline=True)
            embed.add_field(name="Lead Actors", value=self.stringify(content.actors), inline=False)
            embed.add_field(name="Media", value="\n".join(media_info), inline=False)

        elif isinstance(content, plexapi.video.Show):
            """Format the embed being sent for a show"""
            embed = discord.Embed(title=f"{content.title}",
                                  description=f"{content.tagline}", color=0x00ff00)
            embed.add_field(name="Rating", value=rating_string, inline=False)
            embed.add_field(name="Genres", value=self.stringify(content.genres), inline=True)
            embed.add_field(name="Network", value=content.network, inline=True)
            embed.add_field(name="Studio", value=content.studio, inline=True)
            embed.add_field(name="Average Episode Runtime",
                            value=f"{datetime.timedelta(milliseconds=content.duration)}", inline=True)
            embed.add_field(name="Total Seasons", value=content.childCount, inline=True)
            embed.add_field(name="Total Episodes", value=f"{len(content.episodes())}", inline=True)
            # embed.add_field(name="Media", value="\n".join(media_info), inline=False)
            select_thing = Select(
                custom_id=f"content_search_{edit_msg.id}",
                options=[
                    SelectOption(
                        label=f"Season {result.index}",
                        value=f"season_{result.guid}_{hash(result)}",
                        default=False,
                    ) for result in content.seasons()
                ],
            )
            self.bot.component_manager.add_callback(select_thing, self.on_select)

        elif isinstance(content, plexapi.video.Season):
            embed = discord.Embed(title=f"{content.grandparentTitle}",
                                  description=f"Season {content.index}", color=0x00ff00)
            embed.add_field(name="Episodes", value=f"{len(content.episodes())}", inline=True)

        elif isinstance(content, plexapi.video.Episode):

            embed = discord.Embed(title=f"{content.grandparentTitle}\n{content.title}",
                                  description=f"{content.summary}", color=0x00ff00)
            embed.add_field(name="Ratings", value=rating_string, inline=False)
            embed.add_field(name="Directors", value=self.stringify(content.directors), inline=True)
            embed.add_field(name="Writers", value=self.stringify(content.writers), inline=True)
            embed.add_field(name="Lead Actors", value=self.stringify(content.actors), inline=False)
            embed.add_field(name="Media", value="\n".join(media_info), inline=False)

        else:
            embed = discord.Embed(title="Unknown content type", color=0x00ff00)

        if inter is not None:
            await inter.disable_components()

        embed.set_footer(text=f"{content.guid}", icon_url=requester.avatar_url)
        # embed.set_footer(text=f"Requested by {requester.name}", icon_url=requester.avatar_url)
        if select_thing:
            cancel_button = Button(
                label="Cancel",
                style=ButtonStyle.red,
                custom_id=f"cancel_{edit_msg.id}",
            )
            await edit_msg.edit(embed=embed, components=[select_thing, cancel_button])
        else:
            await edit_msg.edit(embed=embed)


def setup(bot):
    bot.add_cog(PlexSearch(bot))
    print(f"Loaded {__name__}")

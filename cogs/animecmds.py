import nextcord
from nextcord.ext import commands, tasks
from nextcord import SlashOption
import aiohttp
import asyncio
import datetime
import json
import os
from typing import Dict, List, Optional
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AnimeNotifications(commands.Cog):
    """
    A Nextcord Cog for tracking anime airing schedules and sending notifications
    when new episodes are released, using the AniList API.
    """

    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.anilist_url = "https://graphql.anilist.co"
        
        # Database setup
        self.db_path = "anime_notifications.db"
        self.setup_database()
        
        # Start the background tasks
        self.check_airing_episodes.start()

    def setup_database(self):
        """Set up the SQLite database for storing subscriptions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
                    # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS anime_subscriptions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            anime_id INTEGER NOT NULL,
            anime_title TEXT NOT NULL,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            UNIQUE(user_id, anime_id, guild_id)
        )
        ''')
        
        # Table to track notified episodes
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notified_episodes (
            id INTEGER PRIMARY KEY,
            anime_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            UNIQUE(anime_id, episode_number)
        )
        ''')
        
        conn.commit()
        conn.close()

    async def cog_load(self):
        """Create aiohttp session when cog loads"""
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Close aiohttp session and cancel tasks when cog unloads"""
        if self.session:
            await self.session.close()
        self.check_airing_episodes.cancel()

    async def fetch_anilist_data(self, query, variables=None):
        """
        Fetch data from AniList GraphQL API
        
        Args:
            query: GraphQL query string
            variables: Variables for the query
            
        Returns:
            JSON response data
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        json_data = {
            'query': query,
            'variables': variables or {}
        }
        
        try:
            async with self.session.post(self.anilist_url, json=json_data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"API error: {response.status}. Details: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {str(e)}")

    @nextcord.slash_command(
        name="anime",
        description="Anime tracking and notifications"
    )
    async def anime_slash(self, interaction: nextcord.Interaction):
        """Root slash command for anime features"""
        # This is just the root command and won't be directly invoked
        pass

    @anime_slash.subcommand(
        name="help",
        description="Get help with anime notification commands"
    )
    async def anime_help(self, interaction: nextcord.Interaction):
        """Displays help information for anime notification commands"""
        embed = nextcord.Embed(
            title="Anime Notification Commands",
            description="Here's how to use the anime notification system:",
            color=nextcord.Color.blue()
        )

        embed.add_field(
            name="/anime search <title>",
            value="Search for anime by title to get its ID",
            inline=False
        )
        embed.add_field(
            name="/anime subscribe <anime_id>",
            value="Subscribe to notifications for a specific anime",
            inline=False
        )
        embed.add_field(
            name="/anime unsubscribe <anime_id>",
            value="Unsubscribe from notifications for an anime",
            inline=False
        )
        embed.add_field(
            name="/anime notify <#channel>",
            value="Set a channel where all your notifications will be sent",
            inline=False
        )
        embed.add_field(
            name="/anime list",
            value="List all your anime subscriptions",
            inline=False
        )

        embed.set_footer(text="Notifications will be sent when new episodes air")
        await interaction.response.send_message(embed=embed)
        
    @anime_slash.subcommand(
        name="search",
        description="Search for an anime by title"
    )
    async def search_anime(
        self,
        interaction: nextcord.Interaction,
        title: str = SlashOption(
            description="Anime title to search for",
            required=True
        )
    ):
        """Search for an anime by title using AniList API"""
        await interaction.response.defer()
        
        query = '''
        query ($search: String) {
            Page(page: 1, perPage: 5) {
                media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
                    id
                    title {
                        romaji
                        english
                        native
                    }
                    coverImage {
                        medium
                    }
                    format
                    status
                    season
                    seasonYear
                    nextAiringEpisode {
                        airingAt
                        timeUntilAiring
                        episode
                    }
                }
            }
        }
        '''
        
        variables = {'search': title}
        
        try:
            data = await self.fetch_anilist_data(query, variables)
            results = data['data']['Page']['media']
            
            if not results:
                await interaction.followup.send("No anime found with that title.")
                return
            
            embed = nextcord.Embed(
                title="Anime Search Results",
                description=f"Results for '{title}'",
                color=nextcord.Color.blue()
            )
            
            for anime in results:
                title_display = anime['title']['english'] or anime['title']['romaji']
                status_text = anime['status'].capitalize().replace('_', ' ')
                
                airing_info = ""
                if anime['nextAiringEpisode']:
                    next_ep = anime['nextAiringEpisode']
                    airing_time = datetime.datetime.fromtimestamp(next_ep['airingAt'])
                    time_until = self.format_time_until(next_ep['timeUntilAiring'])
                    airing_info = f"\nEpisode {next_ep['episode']} airs {time_until}"
                
                embed.add_field(
                    name=f"{title_display} (ID: {anime['id']})",
                    value=f"Status: {status_text}\n"
                          f"Format: {anime['format']}\n"
                          f"Season: {anime['season']} {anime['seasonYear']}"
                          f"{airing_info}",
                    inline=False
                )
                
                if anime['coverImage']['medium']:
                    embed.set_thumbnail(url=anime['coverImage']['medium'])
            
            embed.set_footer(text="Use /anime subscribe <anime_id> to get notifications for new episodes")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error searching for anime: {str(e)}")

    @anime_slash.subcommand(
        name="subscribe",
        description="Subscribe to notifications for new episodes of an anime"
    )
    async def subscribe_anime(
        self,
        interaction: nextcord.Interaction,
        anime_id: int = SlashOption(
            description="AniList ID of the anime (find with /anime search)",
            required=True
        )
    ):
        """Subscribe to notifications for new episodes of an anime"""
        await interaction.response.defer()
        
        # First verify the anime exists and get its info
        query = '''
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                title {
                    romaji
                    english
                }
                status
                nextAiringEpisode {
                    airingAt
                    timeUntilAiring
                    episode
                }
            }
        }
        '''
        
        variables = {'id': anime_id}
        
        try:
            data = await self.fetch_anilist_data(query, variables)
            anime = data['data']['Media']
            
            # Check if anime is currently airing
            if anime['status'] != 'RELEASING':
                await interaction.followup.send("This anime is not currently airing, so you can't subscribe to episode notifications.")
                return
            
            # Get title to display
            title_display = anime['title']['english'] or anime['title']['romaji']
            
            # Save subscription to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO anime_subscriptions (user_id, anime_id, anime_title, guild_id, channel_id) VALUES (?, ?, ?, ?, ?)",
                    (interaction.user.id, anime_id, title_display, interaction.guild_id, interaction.channel_id)
                )
                conn.commit()
                
                # Get next episode info
                next_ep = anime['nextAiringEpisode']
                airing_info = ""
                if next_ep:
                    airing_time = datetime.datetime.fromtimestamp(next_ep['airingAt'])
                    time_until = self.format_time_until(next_ep['timeUntilAiring'])
                    airing_info = f"Episode {next_ep['episode']} airs {time_until}"
                
                embed = nextcord.Embed(
                    title="Anime Subscription Added",
                    description=f"You are now subscribed to notifications for **{title_display}**",
                    color=nextcord.Color.green()
                )
                
                if airing_info:
                    embed.add_field(name="Next Episode", value=airing_info)
                
                embed.set_footer(text="You'll be notified in this channel when new episodes are released")
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                await interaction.followup.send(f"Error adding subscription: {str(e)}")
            finally:
                conn.close()
                
        except Exception as e:
            await interaction.followup.send(f"Error fetching anime information: {str(e)}")

    @anime_slash.subcommand(
        name="unsubscribe",
        description="Unsubscribe from notifications for an anime"
    )
    async def unsubscribe_anime(
        self,
        interaction: nextcord.Interaction,
        anime_id: int = SlashOption(
            description="AniList ID of the anime to unsubscribe from",
            required=True
        )
    ):
        """Unsubscribe from notifications for an anime"""
        await interaction.response.defer()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get the anime title first for the confirmation message
            cursor.execute(
                "SELECT anime_title FROM anime_subscriptions WHERE user_id = ? AND anime_id = ?",
                (interaction.user.id, anime_id)
            )
            result = cursor.fetchone()
            
            if not result:
                await interaction.followup.send("You are not subscribed to this anime.")
                return
            
            anime_title = result[0]
            
            # Delete the subscription
            cursor.execute(
                "DELETE FROM anime_subscriptions WHERE user_id = ? AND anime_id = ?",
                (interaction.user.id, anime_id)
            )
            conn.commit()
            
            embed = nextcord.Embed(
                title="Anime Subscription Removed",
                description=f"You are no longer subscribed to notifications for **{anime_title}**",
                color=nextcord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error removing subscription: {str(e)}")
        finally:
            conn.close()

    @anime_slash.subcommand(
        name="notify",
        description="Set a channel to receive all your anime notifications"
    )
    async def set_notification_channel(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = SlashOption(
            description="Channel to send notifications to",
            required=True,
            channel_types=[nextcord.ChannelType.text]
        )
    ):
        """Set a specific channel to receive all your anime notifications"""
        await interaction.response.defer()
        
        # Verify the user has permission to set notifications in the target channel
        if not channel.permissions_for(interaction.user).send_messages or not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(f"Error: Either you or the bot doesn't have permission to send messages in {channel.mention}.")
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Update all of the user's subscriptions in this guild to use the new channel
            cursor.execute(
                "SELECT COUNT(*) FROM anime_subscriptions WHERE user_id = ? AND guild_id = ?",
                (interaction.user.id, interaction.guild.id)
            )
            subscription_count = cursor.fetchone()[0]
            
            if subscription_count == 0:
                await interaction.followup.send("You don't have any anime subscriptions to update. Subscribe to some anime first with `/anime subscribe`.")
                return
                
            cursor.execute(
                "UPDATE anime_subscriptions SET channel_id = ? WHERE user_id = ? AND guild_id = ?",
                (channel.id, interaction.user.id, interaction.guild.id)
            )
            conn.commit()
            
            embed = nextcord.Embed(
                title="Notification Channel Updated",
                description=f"All your anime notifications will now be sent to {channel.mention}.",
                color=nextcord.Color.green()
            )
            embed.add_field(
                name="Subscriptions Updated", 
                value=f"{subscription_count} anime subscription{'s' if subscription_count != 1 else ''}"
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error updating notification channel: {str(e)}")
        finally:
            conn.close()
    
    @anime_slash.subcommand(
        name="list",
        description="List your anime subscriptions"
    )
    async def list_subscriptions(
        self,
        interaction: nextcord.Interaction
    ):
        """List all anime subscriptions for the user"""
        await interaction.response.defer()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT anime_id, anime_title FROM anime_subscriptions WHERE user_id = ?",
                (interaction.user.id,)
            )
            subscriptions = cursor.fetchall()
            
            if not subscriptions:
                await interaction.followup.send("You have no anime subscriptions.")
                return
            
            embed = nextcord.Embed(
                title="Your Anime Subscriptions",
                description=f"You are subscribed to {len(subscriptions)} anime series",
                color=nextcord.Color.blue()
            )
            
            for anime_id, anime_title in subscriptions:
                # Get next episode info if available
                next_ep_info = await self.get_next_episode_info(anime_id)
                
                if next_ep_info:
                    embed.add_field(
                        name=f"{anime_title} (ID: {anime_id})",
                        value=next_ep_info,
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"{anime_title} (ID: {anime_id})",
                        value="No upcoming episode information available",
                        inline=False
                    )
            
            # Get notification channel info
            cursor.execute(
                "SELECT DISTINCT channel_id FROM anime_subscriptions WHERE user_id = ? AND guild_id = ? LIMIT 1",
                (interaction.user.id, interaction.guild.id)
            )
            channel_result = cursor.fetchone()
            
            if channel_result:
                channel_id = channel_result[0]
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    embed.add_field(
                        name="📢 Notification Channel",
                        value=f"Your notifications will be sent to {channel.mention}",
                        inline=False
                    )
            
            embed.set_footer(text="Use /anime notify to change your notification channel • /anime unsubscribe to remove a subscription")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error listing subscriptions: {str(e)}")
        finally:
            conn.close()

    async def get_next_episode_info(self, anime_id: int) -> Optional[str]:
        """Get information about the next episode for an anime"""
        query = '''
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                nextAiringEpisode {
                    airingAt
                    timeUntilAiring
                    episode
                }
                status
            }
        }
        '''
        
        variables = {'id': anime_id}
        
        try:
            data = await self.fetch_anilist_data(query, variables)
            anime = data['data']['Media']
            
            if anime['status'] != 'RELEASING':
                return "This anime is no longer airing"
            
            next_ep = anime['nextAiringEpisode']
            if next_ep:
                airing_time = datetime.datetime.fromtimestamp(next_ep['airingAt'])
                time_until = self.format_time_until(next_ep['timeUntilAiring'])
                return f"Episode {next_ep['episode']} airs {time_until}\n({airing_time.strftime('%Y-%m-%d %H:%M UTC')})"
            else:
                return None
        except Exception:
            return None

    @tasks.loop(minutes=10)
    async def check_airing_episodes(self):
        """
        Background task that checks for recently aired or upcoming episodes
        and sends notifications to subscribed users
        """
        try:
            # Get all active subscriptions from the database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT anime_id FROM anime_subscriptions")
            anime_ids = [row[0] for row in cursor.fetchall()]
            
            if not anime_ids:
                # No subscriptions, nothing to do
                conn.close()
                return
            
            # Check each anime for new episodes
            for anime_id in anime_ids:
                await self.check_anime_for_notifications(anime_id, conn)
                
                # Sleep briefly between API calls to avoid rate limiting
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"Error in check_airing_episodes task: {str(e)}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    async def check_anime_for_notifications(self, anime_id: int, conn: sqlite3.Connection):
        """Check if an anime has a new episode that needs notifications"""
        query = '''
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                title {
                    romaji
                    english
                }
                status
                nextAiringEpisode {
                    airingAt
                    timeUntilAiring
                    episode
                }
                airingSchedule {
                    nodes {
                        airingAt
                        timeUntilAiring
                        episode
                    }
                }
            }
        }
        '''
        
        variables = {'id': anime_id}
        
        try:
            data = await self.fetch_anilist_data(query, variables)
            anime = data['data']['Media']
            
            if anime['status'] != 'RELEASING':
                return  # Anime is not currently airing
                
            # Get episodes that have aired in the last 30 minutes
            # (This gives some buffer for API delays and our check interval)
            current_time = datetime.datetime.now().timestamp()
            recently_aired = []
            
            for node in anime['airingSchedule']['nodes']:
                # Check if episode aired in the last 30 minutes
                time_since_aired = current_time - node['airingAt']
                if 0 <= time_since_aired <= 1800:  # 30 minutes in seconds
                    recently_aired.append(node)
            
            cursor = conn.cursor()
            
            for episode in recently_aired:
                # Check if we've already notified for this episode
                cursor.execute(
                    "SELECT id FROM notified_episodes WHERE anime_id = ? AND episode_number = ?",
                    (anime_id, episode['episode'])
                )
                
                if cursor.fetchone():
                    continue  # Already notified
                
                # Get all users subscribed to this anime
                cursor.execute(
                    "SELECT user_id, guild_id, channel_id FROM anime_subscriptions WHERE anime_id = ?",
                    (anime_id,)
                )
                
                subscriptions = cursor.fetchall()
                title_display = anime['title']['english'] or anime['title']['romaji']
                
                # Send notifications to all subscribed users
                for user_id, guild_id, channel_id in subscriptions:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if not channel:
                            continue
                            
                        embed = nextcord.Embed(
                            title="🎬 New Anime Episode Released!",
                            description=f"**{title_display}** Episode {episode['episode']} is now available!",
                            color=nextcord.Color.gold(),
                            timestamp=datetime.datetime.fromtimestamp(episode['airingAt'])
                        )
                        
                        # Add a mention for the user
                        await channel.send(f"<@{user_id}>", embed=embed)
                        
                    except Exception as e:
                        print(f"Error sending notification: {str(e)}")
                
                # Mark this episode as notified
                cursor.execute(
                    "INSERT OR IGNORE INTO notified_episodes (anime_id, episode_number) VALUES (?, ?)",
                    (anime_id, episode['episode'])
                )
                conn.commit()
                
        except Exception as e:
            print(f"Error checking anime {anime_id}: {str(e)}")

    @check_airing_episodes.before_loop
    async def before_check_airing_episodes(self):
        """Wait until the bot is ready before starting the background task"""
        await self.bot.wait_until_ready()

    def format_time_until(self, seconds: int) -> str:
        """Format seconds until airing into a readable string"""
        if seconds < 0:
            return "already aired"
            
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 and days == 0:  # Only show minutes if less than a day
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            
        if not parts:
            return "very soon"
            
        return "in " + ", ".join(parts)

# Function to setup the cog
def setup(bot):
    bot.add_cog(AnimeNotifications(bot))
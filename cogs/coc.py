import nextcord
from nextcord.ext import commands
from nextcord import SlashOption
import aiohttp
import asyncio
import datetime
import urllib.parse
import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv("tkn.env")

class ClashOfClans(commands.Cog):
    """
    A Nextcord Cog for fetching Clash of Clans data including player stats, clan wars,
    and clan war league information using the official Clash of Clans API.
    """

    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("COC_API_KEY")  # Get API key from environment variable
        if not self.api_key:
            print("WARNING: COC_API_KEY environment variable not set. Clash of Clans commands will not work.")
        
        self.base_url = "https://api.clashofclans.com/v1"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.session = None
        # Store the last known season ID to detect season changes
        self.last_season_id = None
        # Store legend league reset time (will be updated dynamically)
        self.legend_reset_time = None

    async def cog_load(self):
        """Create aiohttp session when cog loads"""
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Close aiohttp session when cog unloads"""
        if self.session:
            await self.session.close()

    async def fetch_data(self, endpoint: str) -> Dict[str, Any]:
        """
        Fetches data from the Clash of Clans API.

        Args:
            endpoint: The API endpoint to query

        Returns:
            Dictionary containing the API response
        """
        if not self.api_key:
            raise Exception("COC_API_KEY environment variable not set")
            
        url = f"{self.base_url}/{endpoint}"

        # Create a session if one doesn't exist
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            async with self.session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    error_text = await response.text()
                    raise Exception(f"Invalid API key or unauthorized access. Details: {error_text}")
                elif response.status == 404:
                    error_text = await response.text()
                    raise Exception(f"Resource not found. Details: {error_text}")
                else:
                    error_text = await response.text()
                    raise Exception(f"API error: {response.status}. Details: {error_text}")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {str(e)}")

    @nextcord.slash_command(
        name="coc",
        description="Access Clash of Clans information"
    )
    async def coc_slash(self, interaction: nextcord.Interaction):
        """Root slash command for Clash of Clans"""
        # This is just the root command and won't be directly invoked
        pass

    @coc_slash.subcommand(
        name="help",
        description="Get help with Clash of Clans commands"
    )
    async def coc_help(self, interaction: nextcord.Interaction):
        """Displays help information for Clash of Clans commands"""
        embed = nextcord.Embed(
            title="Clash of Clans Bot Commands",
            description="Here's how to use the Clash of Clans slash commands:",
            color=nextcord.Color.gold()
        )

        embed.add_field(
            name="/coc player",
            value="Get detailed stats for a player",
            inline=False
        )
        embed.add_field(
            name="/coc clan",
            value="Get information about a clan",
            inline=False
        )
        embed.add_field(
            name="/coc war",
            value="Get current war information for a clan",
            inline=False
        )
        embed.add_field(
            name="/coc cwl",
            value="Get Clan War League information for a clan",
            inline=False
        )
        embed.add_field(
            name="/coc leagueday",
            value="Get Legend League attack results for a player",
            inline=False
        )

        embed.set_footer(text="Note: Player and clan tags should include the # symbol")
        await interaction.response.send_message(embed=embed)

    @coc_slash.subcommand(
        name="player",
        description="Get detailed stats for a Clash of Clans player"
    )
    async def get_player(
        self, 
        interaction: nextcord.Interaction, 
        player_tag: str = SlashOption(
            description="Player tag including #",
            required=True
        )
    ):
        """Get detailed stats for a player"""
        await interaction.response.defer()

        try:
            # URL encode the player tag
            encoded_tag = urllib.parse.quote(player_tag)
            player_data = await self.fetch_data(f"players/{encoded_tag}")

            # Create embed with player info
            embed = nextcord.Embed(
                title=f"{player_data['name']} ({player_data['tag']})",
                description=f"TH{player_data['townHallLevel']} | XP: {player_data['expLevel']}",
                color=nextcord.Color.gold()
            )

            # Add trophy info
            embed.add_field(
                name="🏆 Trophies",
                value=f"Current: {player_data['trophies']}\nBest: {player_data['bestTrophies']}",
                inline=True
            )

            # Add war stars
            embed.add_field(
                name="⭐ War Stars",
                value=player_data.get('warStars', 'N/A'),
                inline=True
            )

            # Add attack/defense wins if available
            if 'attackWins' in player_data:
                embed.add_field(
                    name="🗡️ Attack Wins",
                    value=player_data['attackWins'],
                    inline=True
                )

            if 'defenseWins' in player_data:
                embed.add_field(
                    name="🛡️ Defense Wins",
                    value=player_data['defenseWins'],
                    inline=True
                )

            # Add clan info if player is in a clan
            if 'clan' in player_data:
                clan_info = player_data['clan']
                embed.add_field(
                    name="🏰 Clan",
                    value=f"[{clan_info['name']}]({clan_info.get('tag', 'N/A')})\n{clan_info.get('role', 'Member')}",
                    inline=False
                )

                if 'badgeUrls' in clan_info and 'medium' in clan_info['badgeUrls']:
                    embed.set_thumbnail(url=clan_info['badgeUrls']['medium'])

            # Add troops donated/received
            embed.add_field(
                name="🎁 Donations",
                value=f"Given: {player_data.get('donations', 0)}\nReceived: {player_data.get('donationsReceived', 0)}",
                inline=False
            )

            # Add hero levels if available
            if 'heroes' in player_data and player_data['heroes']:
                heroes_text = []
                for hero in player_data['heroes']:
                    heroes_text.append(f"{hero['name']}: Lvl {hero['level']}")

                embed.add_field(
                    name="👑 Heroes",
                    value="\n".join(heroes_text) if heroes_text else "None",
                    inline=False
                )

            # Add league info if available
            if 'league' in player_data and player_data['league']:
                embed.set_footer(
                    text=f"League: {player_data['league']['name']}",
                    icon_url=player_data['league']['iconUrls']['small'] if 'iconUrls' in player_data['league'] else None
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error fetching player data: {str(e)}")

    @coc_slash.subcommand(
        name="clan",
        description="Get information about a Clash of Clans clan"
    )
    async def get_clan(
        self, 
        interaction: nextcord.Interaction, 
        clan_tag: str = SlashOption(
            description="Clan tag including #",
            required=True
        )
    ):
        """Get information about a clan"""
        await interaction.response.defer()

        try:
            # URL encode the clan tag
            encoded_tag = urllib.parse.quote(clan_tag)
            clan_data = await self.fetch_data(f"clans/{encoded_tag}")

            # Create embed with clan info
            embed = nextcord.Embed(
                title=f"{clan_data['name']} ({clan_data['tag']})",
                description=clan_data.get('description', 'No description'),
                color=nextcord.Color.dark_green()
            )

            # Add clan level and member info
            embed.add_field(
                name="ℹ️ Basic Info",
                value=f"Level: {clan_data['clanLevel']}\n"
                      f"Members: {clan_data['members']}/50\n"
                      f"Type: {clan_data['type']}\n"
                      f"War Frequency: {clan_data.get('warFrequency', 'N/A')}",
                inline=True
            )

            # Add war record
            embed.add_field(
                name="⚔️ War Record",
                value=f"Wins: {clan_data.get('warWins', 'N/A')}\n"
                      f"Losses: {clan_data.get('warLosses', 'N/A')}\n"
                      f"Ties: {clan_data.get('warTies', 'N/A')}\n"
                      f"Win Streak: {clan_data.get('warWinStreak', 'N/A')}",
                inline=True
            )

            # Add location if available
            if 'location' in clan_data and clan_data['location']:
                embed.add_field(
                    name="📍 Location",
                    value=clan_data['location']['name'],
                    inline=True
                )

            # Add required trophies and clan points
            embed.add_field(
                name="🏆 Requirements & Points",
                value=f"Required Trophies: {clan_data.get('requiredTrophies', 'N/A')}\n"
                      f"Required TH: {clan_data.get('requiredTownhallLevel', 'N/A')}\n"
                      f"Clan Points: {clan_data.get('clanPoints', 'N/A')}\n"
                      f"Capital Points: {clan_data.get('clanCapitalPoints', 'N/A')}",
                inline=True
            )

            # Add clan labels if available
            if 'labels' in clan_data and clan_data['labels']:
                label_names = [label['name'] for label in clan_data['labels']]
                embed.add_field(
                    name="🏷️ Labels",
                    value=", ".join(label_names),
                    inline=False
                )

            # Set clan badge as thumbnail
            if 'badgeUrls' in clan_data and 'medium' in clan_data['badgeUrls']:
                embed.set_thumbnail(url=clan_data['badgeUrls']['medium'])

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error fetching clan data: {str(e)}")

    @coc_slash.subcommand(
        name="war",
        description="Get current war information for a Clash of Clans clan"
    )
    async def get_current_war(
        self, 
        interaction: nextcord.Interaction, 
        clan_tag: str = SlashOption(
            description="Clan tag including #",
            required=True
        )
    ):
        """Get current war information for a clan"""
        await interaction.response.defer()

        try:
            # URL encode the clan tag
            encoded_tag = urllib.parse.quote(clan_tag)
            war_data = await self.fetch_data(f"clans/{encoded_tag}/currentwar")

            # Check war state
            if war_data.get('state') == 'notInWar':
                await interaction.followup.send("This clan is not currently in a war.")
                return

            # Get clan data
            clan = war_data['clan']
            opponent = war_data['opponent']

            # Create embed
            embed = nextcord.Embed(
                title=f"War: {clan['name']} vs {opponent['name']}",
                description=f"War State: {war_data['state']}",
                color=nextcord.Color.red()
            )

            # Add team size
            embed.add_field(
                name="🏰 War Size",
                value=f"{war_data['teamSize']} vs {war_data['teamSize']}",
                inline=False
            )

            # Add attack counts
            embed.add_field(
                name=f"{clan['name']} ({clan['tag']})",
                value=f"⭐ Stars: {clan['stars']}\n"
                      f"💥 Destruction: {clan['destructionPercentage']}%\n"
                      f"🗡️ Attacks Used: {clan.get('attacks', 0)}/{war_data['teamSize'] * 2}",
                inline=True
            )

            embed.add_field(
                name=f"{opponent['name']} ({opponent['tag']})",
                value=f"⭐ Stars: {opponent['stars']}\n"
                      f"💥 Destruction: {opponent['destructionPercentage']}%\n"
                      f"🗡️ Attacks Used: {opponent.get('attacks', 0)}/{war_data['teamSize'] * 2}",
                inline=True
            )

            # Add war timing information
            if 'preparationStartTime' in war_data:
                prep_time = datetime.datetime.strptime(
                    war_data['preparationStartTime'], '%Y%m%dT%H%M%S.%fZ'
                )
                start_time = datetime.datetime.strptime(
                    war_data['startTime'], '%Y%m%dT%H%M%S.%fZ'
                )
                end_time = datetime.datetime.strptime(
                    war_data['endTime'], '%Y%m%dT%H%M%S.%fZ'
                )

                now = datetime.datetime.utcnow()

                # Determine current war phase and time remaining
                time_info = ""
                if now < start_time:
                    # Preparation phase
                    remaining = start_time - now
                    time_info = f"Preparation Phase\nWar starts in: {self.format_timedelta(remaining)}"
                elif now < end_time:
                    # Battle day
                    remaining = end_time - now
                    time_info = f"Battle Day\nWar ends in: {self.format_timedelta(remaining)}"
                else:
                    # War ended
                    time_info = "War has ended"

                embed.add_field(
                    name="⏱️ War Timeline",
                    value=time_info,
                    inline=False
                )

            # Set clan badge as thumbnail
            if 'badgeUrls' in clan and 'medium' in clan['badgeUrls']:
                embed.set_thumbnail(url=clan['badgeUrls']['medium'])

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error fetching war data: {str(e)}")

    @coc_slash.subcommand(
        name="cwl",
        description="Get Clan War League information for a Clash of Clans clan"
    )
    async def get_cwl(
        self, 
        interaction: nextcord.Interaction, 
        clan_tag: str = SlashOption(
            description="Clan tag including #",
            required=True
        )
    ):
        """Get Clan War League information for a clan"""
        await interaction.response.defer()

        try:
            # URL encode the clan tag
            encoded_tag = urllib.parse.quote(clan_tag)

            # First, check if CWL is active
            cwl_data = await self.fetch_data(f"clans/{encoded_tag}/currentwar/leaguegroup")

            if cwl_data.get('state') == 'notInWar':
                await interaction.followup.send("This clan is not currently participating in Clan War League.")
                return

            # Create embed with CWL group info
            embed = nextcord.Embed(
                title="Clan War League Information",
                description=f"Season: {cwl_data.get('season', 'Current')}",
                color=nextcord.Color.purple()
            )

            # Add basic group info
            embed.add_field(
                name="📋 Group Information",
                value=f"State: {cwl_data['state']}\n"
                      f"Clans in Group: {len(cwl_data['clans'])}",
                inline=False
            )

            # List clans in the group
            clan_list = []
            for i, clan in enumerate(cwl_data['clans']):
                clan_list.append(f"{i+1}. {clan['name']} ({clan['tag']})")

            embed.add_field(
                name="🏰 Participating Clans",
                value="\n".join(clan_list[:10]) + 
                      ("\n..." if len(clan_list) > 10 else ""),
                inline=False
            )

            # Add rounds info if available
            if 'rounds' in cwl_data and cwl_data['rounds']:
                rounds_info = []
                for i, round_data in enumerate(cwl_data['rounds']):
                    war_tags = len(round_data['warTags'])
                    rounds_info.append(f"Round {i+1}: {war_tags} wars")

                embed.add_field(
                    name="🔄 Rounds",
                    value="\n".join(rounds_info),
                    inline=False
                )

            await interaction.followup.send(embed=embed)

            # Try to get current CWL war information
            try:
                cwl_war_data = await self.fetch_data(f"clans/{encoded_tag}/currentwar")

                if cwl_war_data.get('state') != 'notInWar' and cwl_war_data.get('isWarLeague', False):
                    # Create embed for current CWL war
                    war_embed = nextcord.Embed(
                        title=f"Current CWL War",
                        description=f"{cwl_war_data['clan']['name']} vs {cwl_war_data['opponent']['name']}",
                        color=nextcord.Color.gold()
                    )

                    # Add basic war info
                    war_embed.add_field(
                        name="⚔️ War Information",
                        value=f"State: {cwl_war_data['state']}\n"
                              f"Team Size: {cwl_war_data['teamSize']}",
                        inline=False
                    )

                    # Add scores
                    clan = cwl_war_data['clan']
                    opponent = cwl_war_data['opponent']

                    war_embed.add_field(
                        name=f"{clan['name']}",
                        value=f"⭐ Stars: {clan['stars']}\n"
                              f"💥 Destruction: {clan['destructionPercentage']}%",
                        inline=True
                    )

                    war_embed.add_field(
                        name=f"{opponent['name']}",
                        value=f"⭐ Stars: {opponent['stars']}\n"
                              f"💥 Destruction: {opponent['destructionPercentage']}%",
                        inline=True
                    )

                    # Send the additional embed
                    await interaction.followup.send(embed=war_embed)
            except Exception as e:
                # If we can't get the current war info, just continue
                pass

        except Exception as e:
            await interaction.followup.send(f"Error fetching CWL data: {str(e)}")

    @coc_slash.subcommand(
        name="leagueday",
        description="Get Legend League attack results for a player"
    )
    async def get_legend_league_day(
        self,
        interaction: nextcord.Interaction,
        player_tag: str = SlashOption(
            description="Player tag including #",
            required=True
        )
    ):
        """Get Legend League attack results for a player"""
        await interaction.response.defer()

        try:
            # URL encode the player tag
            encoded_tag = urllib.parse.quote(player_tag)
            player_data = await self.fetch_data(f"players/{encoded_tag}")

            # Check if player is in Legend League
            is_legend = False
            league_name = "Unknown"
            league_icon = None

            if 'league' in player_data and player_data['league']:
                league_name = player_data['league']['name']
                if 'iconUrls' in player_data['league']:
                    league_icon = player_data['league']['iconUrls'].get('small')

                is_legend = "Legend" in league_name

            if not is_legend:
                embed = nextcord.Embed(
                    title="Not in Legend League",
                    description=f"{player_data['name']} is currently in {league_name}, not Legend League.",
                    color=nextcord.Color.red()
                )
                if league_icon:
                    embed.set_thumbnail(url=league_icon)
                await interaction.followup.send(embed=embed)
                return

            # Get Legend League Season information
            if 'legendStatistics' not in player_data:
                await interaction.followup.send(f"{player_data['name']} has no Legend League statistics available.")
                return

            legend_stats = player_data['legendStatistics']
            current_season = legend_stats.get('currentSeason', {})

            # Check for a season change
            current_season_id = legend_stats.get('legendSeasonId', None)
            if current_season_id != self.last_season_id:
                # Season changed, reset the cached reset time
                self.legend_reset_time = None
                self.last_season_id = current_season_id

            # Determine the current season's reset time if not already set
            if self.legend_reset_time is None:
                # Try to intelligently determine the Legend League reset time
                # based on available information
                self.legend_reset_time = self.determine_legend_reset_time(player_data)

            # Get attack and defense stats
            attacks_used = current_season.get('attacks', 0)
            attacks_remaining = 8 - attacks_used
            trophies_gained = current_season.get('trophiesGained', 0)
            defenses_done = current_season.get('defenses', 0)
            trophies_lost = current_season.get('trophiesLost', 0)

            # Create embed
            embed = nextcord.Embed(
                title=f"Legend League Day - {player_data['name']}",
                description=f"Current Trophies: {player_data['trophies']}",
                color=nextcord.Color.gold()
            )

            # Add basic stats
            embed.add_field(
                name="🗡️ Attacks",
                value=f"Used: {attacks_used}/8\n"
                      f"Remaining: {attacks_remaining}\n"
                      f"Trophies Gained: +{trophies_gained}",
                inline=True
            )

            embed.add_field(
                name="🛡️ Defenses",
                value=f"Completed: {defenses_done}/8\n"
                      f"Trophies Lost: -{trophies_lost}",
                inline=True
            )

            # Calculate net trophy change
            net_change = trophies_gained - trophies_lost
            change_symbol = "+" if net_change >= 0 else ""

            embed.add_field(
                name="📊 Summary",
                value=f"Net Trophy Change: {change_symbol}{net_change}\n"
                      f"Average per Attack: {self.avg_per_attack(trophies_gained, attacks_used)}\n"
                      f"Average per Defense: {self.avg_per_defense(trophies_lost, defenses_done)}",
                inline=False
            )

            # Get individual attack/defense records if available
            # Note: The Clash of Clans API doesn't currently provide individual attack/defense details

            # Set legend league icon as thumbnail
            if league_icon:
                embed.set_thumbnail(url=league_icon)

            # Add daily reset countdown
            now = datetime.datetime.utcnow()
            if self.legend_reset_time and self.legend_reset_time > now:
                time_until_reset = self.legend_reset_time - now
                embed.set_footer(text=f"Daily reset in: {self.format_timedelta(time_until_reset)}")
            else:
                # If we couldn't determine the reset time or it's in the past
                embed.set_footer(text="Legend League reset time could not be determined precisely")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"Error fetching Legend League data: {str(e)}")

    def avg_per_attack(self, trophies_gained: int, attacks_used: int) -> str:
        """Calculate average trophies per attack"""
        if attacks_used == 0:
            return "N/A"
        return f"+{trophies_gained / attacks_used:.1f}"

    def avg_per_defense(self, trophies_lost: int, defenses_done: int) -> str:
        """Calculate average trophies per defense"""
        if defenses_done == 0:
            return "N/A"
        return f"-{trophies_lost / defenses_done:.1f}"

    def determine_legend_reset_time(self, player_data: Dict[str, Any]) -> Optional[datetime.datetime]:
        """
        Intelligently determine the Legend League reset time based on player data
        and current attacks/defenses.

        This method attempts to determine the reset time by analyzing patterns in the
        player's Legend League statistics and the current UTC time.

        Args:
            player_data: Player data from the API

        Returns:
            datetime object for the next reset time, or None if it can't be determined
        """
        if 'legendStatistics' not in player_data:
            return None

        legend_stats = player_data['legendStatistics']
        current_season = legend_stats.get('currentSeason', {})

        # Default reset hour is 5:00 UTC (standard for most in-game events)
        # but it can vary especially during season transitions
        now = datetime.datetime.utcnow()
        reset_hour = 5  # Default

        # If it's early in the legend day (few or no attacks/defenses), 
        # the reset likely just happened
        attacks = current_season.get('attacks', 0)
        defenses = current_season.get('defenses', 0)

        if attacks == 0 and defenses == 0:
            # If no attacks or defenses yet, we're probably early in the legend day
            # Reset time is likely within the last few hours
            hours_ago = [1, 2, 3, 4, 5, 6]  # Check reasonable time ranges

            for hours in hours_ago:
                potential_reset = now - datetime.timedelta(hours=hours)
                # If this looks like a plausible reset time, use it
                if potential_reset.minute < 15:  # Reset times are usually on the hour
                    reset_hour = potential_reset.hour
                    break

        # Construct the next reset time
        reset_time = datetime.datetime(now.year, now.month, now.day, reset_hour, 0, 0)  
         # If the reset time is in the past, move to tomorrow
        if reset_time < now:
            reset_time += datetime.timedelta(days=1)
            
        return reset_time
    
    def format_timedelta(self, delta: datetime.timedelta) -> str:
        """Format a timedelta object into a readable string"""
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
            
    @coc_slash.subcommand(
        name="season",
        description="Get Legend League season information"
    )
    async def get_legend_season(
        self,
        interaction: nextcord.Interaction,
        player_tag: str = SlashOption(
            description="Player tag including #",
            required=True
        ),
        season_id: str = SlashOption(
            description="Season ID (YYYY-MM) or 'previous' for last season",
            required=False,
            default="current"
        )
    ):
        """Get Legend League season information for a player"""
        await interaction.response.defer()
        
        try:
            # URL encode the player tag
            encoded_tag = urllib.parse.quote(player_tag)
            player_data = await self.fetch_data(f"players/{encoded_tag}")
            
            # Check if player has legend statistics
            if 'legendStatistics' not in player_data:
                await interaction.followup.send(f"{player_data['name']} has no Legend League statistics available.")
                return
            
            legend_stats = player_data['legendStatistics']
            
            # Determine which season to display
            if season_id.lower() == "current":
                # Show current season
                if 'currentSeason' not in legend_stats:
                    await interaction.followup.send(f"{player_data['name']} has no current Legend League season data.")
                    return
                    
                season_data = legend_stats['currentSeason']
                season_title = "Current Season"
                
            elif season_id.lower() == "previous" or season_id.lower() == "last":
                # Show previous season
                if 'previousSeason' not in legend_stats:
                    await interaction.followup.send(f"{player_data['name']} has no previous Legend League season data.")
                    return
                    
                season_data = legend_stats['previousSeason']
                season_id = season_data.get('id', 'Previous')
                season_title = f"Season {season_id}"
                
            else:
                # Try to find specified season in previous seasons list
                if 'previousSeasons' not in legend_stats:
                    await interaction.followup.send(f"{player_data['name']} has no previous Legend League seasons data.")
                    return
                    
                season_found = False
                for season in legend_stats['previousSeasons']:
                    if season.get('id') == season_id:
                        season_data = season
                        season_found = True
                        break
                        
                if not season_found:
                    await interaction.followup.send(f"Could not find season {season_id} for {player_data['name']}.")
                    return
                    
                season_title = f"Season {season_id}"
            
            # Create embed with season info
            embed = nextcord.Embed(
                title=f"Legend League Season - {player_data['name']}",
                description=season_title,
                color=nextcord.Color.gold()
            )
            
            # Add season stats
            embed.add_field(
                name="🏆 Ranking",
                value=f"Rank: {season_data.get('rank', 'Unranked')}\n"
                      f"Trophies: {season_data.get('trophies', 0)}",
                inline=True
            )
            
            # Add additional stats if available for current season
            if season_id.lower() == "current":
                embed.add_field(
                    name="📊 Current Season Stats",
                    value=f"Attacks: {season_data.get('attacks', 0)}/8\n"
                          f"Defenses: {season_data.get('defenses', 0)}/8\n"
                          f"Gained: +{season_data.get('trophiesGained', 0)}\n"
                          f"Lost: -{season_data.get('trophiesLost', 0)}",
                    inline=True
                )
                
                # Calculate net trophy change
                net_change = season_data.get('trophiesGained', 0) - season_data.get('trophiesLost', 0)
                change_symbol = "+" if net_change >= 0 else ""
                
                embed.add_field(
                    name="📈 Net Change",
                    value=f"{change_symbol}{net_change} trophies",
                    inline=True
                )
            
            # Set league icon as thumbnail
            if 'league' in player_data and 'iconUrls' in player_data['league']:
                league_icon = player_data['league']['iconUrls'].get('small')
                if league_icon:
                    embed.set_thumbnail(url=league_icon)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error fetching Legend League season data: {str(e)}")
            
    @coc_slash.subcommand(
        name="capital",
        description="Get Clan Capital information for a clan"
    )
    async def get_clan_capital(
        self,
        interaction: nextcord.Interaction,
        clan_tag: str = SlashOption(
            description="Clan tag including #",
            required=True
        )
    ):
        """Get Clan Capital information for a clan"""
        await interaction.response.defer()
        
        try:
            # URL encode the clan tag
            encoded_tag = urllib.parse.quote(clan_tag)
            clan_data = await self.fetch_data(f"clans/{encoded_tag}")
            
            # Check if clan has capital data
            if 'clanCapital' not in clan_data:
                await interaction.followup.send(f"{clan_data['name']} has no Clan Capital data available.")
                return
            
            capital_data = clan_data['clanCapital']
            
            # Create embed with capital info
            embed = nextcord.Embed(
                title=f"Clan Capital - {clan_data['name']}",
                description=f"Capital Hall Level: {capital_data.get('capitalHallLevel', 0)}",
                color=nextcord.Color.blue()
            )
            
            # Add capital points info
            embed.add_field(
                name="💰 Capital Resources",
                value=f"Capital Points: {clan_data.get('clanCapitalPoints', 0)}",
                inline=False
            )
            
            # Add districts information if available
            if 'districts' in capital_data:
                districts_text = []
                for district in capital_data['districts']:
                    districts_text.append(f"{district['name']}: Level {district['districtHallLevel']}")
                
                embed.add_field(
                    name="🏙️ Districts",
                    value="\n".join(districts_text) if districts_text else "None",
                    inline=False
                )
            
            # Add raid stats if available
            if 'capitalRaidSeasons' in clan_data and clan_data['capitalRaidSeasons']:
                latest_raid = clan_data['capitalRaidSeasons'][0]
                
                raid_text = (
                    f"Total Attacks: {latest_raid.get('attackCount', 0)}\n"
                    f"Enemy Districts Destroyed: {latest_raid.get('enemyDistrictsDestroyed', 0)}\n"
                    f"Offensive Raid Medals: {latest_raid.get('offensiveReward', 0)}\n"
                    f"Defensive Raid Medals: {latest_raid.get('defensiveReward', 0)}"
                )
                
                embed.add_field(
                    name="⚔️ Latest Raid Weekend",
                    value=raid_text,
                    inline=False
                )
                
                # If raid weekend is active
                if 'state' in latest_raid and latest_raid['state'] != 'ended':
                    embed.add_field(
                        name="🔄 Current Raid Status",
                        value=f"State: {latest_raid['state'].capitalize()}",
                        inline=False
                    )
            
            # Set clan badge as thumbnail
            if 'badgeUrls' in clan_data and 'medium' in clan_data['badgeUrls']:
                embed.set_thumbnail(url=clan_data['badgeUrls']['medium'])
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error fetching Clan Capital data: {str(e)}")
    
    @coc_slash.subcommand(
        name="members",
        description="List members of a Clash of Clans clan"
    )
    async def list_clan_members(
        self,
        interaction: nextcord.Interaction,
        clan_tag: str = SlashOption(
            description="Clan tag including #",
            required=True
        ),
        sort_by: str = SlashOption(
            description="Sort members by",
            choices=["trophies", "role", "donations", "name"],
            required=False,
            default="trophies"
        )
    ):
        """List members of a clan with sorting options"""
        await interaction.response.defer()
        
        try:
            # URL encode the clan tag
            encoded_tag = urllib.parse.quote(clan_tag)
            clan_data = await self.fetch_data(f"clans/{encoded_tag}")
            
            # Check if clan has members
            if 'members' not in clan_data or clan_data['members'] == 0:
                await interaction.followup.send(f"{clan_data['name']} has no members.")
                return
            
            # Get member list
            members_data = clan_data['memberList']
            
            # Sort members according to preference
            if sort_by == "trophies":
                sorted_members = sorted(members_data, key=lambda m: m.get('trophies', 0), reverse=True)
            elif sort_by == "role":
                # Define role hierarchy
                role_hierarchy = {"leader": 0, "coLeader": 1, "admin": 2, "member": 3}
                sorted_members = sorted(members_data, key=lambda m: role_hierarchy.get(m.get('role', 'member'), 999))
            elif sort_by == "donations":
                sorted_members = sorted(members_data, key=lambda m: m.get('donations', 0), reverse=True)
            elif sort_by == "name":
                sorted_members = sorted(members_data, key=lambda m: m.get('name', '').lower())
            else:
                # Default to trophy sorting
                sorted_members = sorted(members_data, key=lambda m: m.get('trophies', 0), reverse=True)
            
            # Create embed with clan info
            embed = nextcord.Embed(
                title=f"Members of {clan_data['name']}",
                description=f"Total Members: {clan_data['members']}/50",
                color=nextcord.Color.green()
            )
            
            # Add sorted members (up to 25 to stay within Discord limits)
            members_text = []
            for i, member in enumerate(sorted_members[:25]):
                role_icon = "👑" if member['role'] == "leader" else "🎯" if member['role'] == "coLeader" else "🛡️" if member['role'] == "admin" else "👤"
                members_text.append(
                    f"{i+1}. {role_icon} {member['name']} (TH{member.get('townhallLevel', '?')})"
                    f" - {member['trophies']} 🏆 | {member.get('donations', 0)} 🎁"
                )
            
            # Add indication if there are more members
            if len(sorted_members) > 25:
                members_text.append(f"... and {len(sorted_members) - 25} more members")
            
            embed.add_field(
                name=f"Members (Sorted by {sort_by})",
                value="\n".join(members_text),
                inline=False
            )
            
            # Set clan badge as thumbnail
            if 'badgeUrls' in clan_data and 'medium' in clan_data['badgeUrls']:
                embed.set_thumbnail(url=clan_data['badgeUrls']['medium'])
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"Error fetching clan members: {str(e)}")

# Function to setup the cog
def setup(bot):
    bot.add_cog(ClashOfClans(bot))
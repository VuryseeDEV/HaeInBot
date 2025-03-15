import nextcord
from nextcord.ext import commands
import httpx
import asyncio
import datetime
import urllib.parse
import json
from typing import Optional, List, Dict, Any

class ClashLegendsStats(commands.Cog):
    """Cog for tracking Clash of Clans Legend League statistics using ClashKing API"""

    def __init__(self, bot):
        self.bot = bot
        self.api_base_url = "https://api.clashk.ing"
        self.http_client = httpx.AsyncClient(
            timeout=30.0, 
            headers={"accept": "application/json"}
        )

    def cog_unload(self):
        """Clean up the HTTP client when the cog is unloaded"""
        asyncio.create_task(self.http_client.aclose())

    async def fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch data from a direct URL"""
        try:
            response = await self.http_client.get(url)
            if response.status_code != 200:
                return {"error": f"API returned status code {response.status_code}"}
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching data from {url}: {e}")
            return {"error": f"HTTP error: {str(e)}"}
        except json.JSONDecodeError:
            return {"error": "Failed to parse API response as JSON"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    @nextcord.slash_command(name="legends", description="Commands related to Clash of Clans Legend League statistics")
    async def legends(self, interaction: nextcord.Interaction):
        """Base legends command group"""
        # This will never be called directly as it has subcommands
        pass

    @legends.subcommand(name="day", description="Show a player's Legend League day stats")
    async def legends_day(
        self, 
        interaction: nextcord.Interaction,
        player_tag: str = nextcord.SlashOption(
            name="player_tag",
            description="Player tag (e.g., #2PJRYJLG9)",
            required=True
        ),
        date: str = nextcord.SlashOption(
            name="date",
            description="Date in YYYY-MM-DD format (optional, defaults to today)",
            required=False
        )
    ):
        """Show a player's Legend League attacks, defenses, and trophy changes for a day"""
        await interaction.response.defer()

        # Format tag - ensure it has # and encode it properly
        tag = player_tag.strip()
        if not tag.startswith("#"):
            tag = f"#{tag}"
        
        # URL encode the tag (# becomes %23)
        encoded_tag = urllib.parse.quote(tag)
        
        # Construct the URL - based on the working endpoint
        url = f"{self.api_base_url}/player/{encoded_tag}/legends"
        
        # Make API request to get player data
        data = await self.fetch_data(url)
        
        if "error" in data:
            await interaction.followup.send(f"❌ Failed to fetch Legend League data for player {tag}.\nError: {data['error']}")
            return

        # Get player name and townhall info
        player_name = data.get("name", f"Player {tag}")
        townhall_level = data.get("townhall", "?")
        
        # Format date or use today's date if not provided
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            
        # Check if player has legend stats for the requested date
        legends_data = data.get("legends", {})
        if not legends_data:
            await interaction.followup.send(f"This player has no Legend League history.")
            return
            
        if date not in legends_data:
            # If we don't have data for the requested date, get the most recent date
            available_dates = sorted(legends_data.keys(), reverse=True)
            if not available_dates:
                await interaction.followup.send(f"This player is not in Legend League at this moment.")
                return
            date = available_dates[0]
        
        day_data = legends_data.get(date, {})
        if not day_data:
            await interaction.followup.send(f"No Legend League data available for {player_name} on {date}.")
            return
        
        # Extract attack and defense data from the day's data
        attacks_raw = day_data.get("new_attacks", [])
        defenses_raw = day_data.get("new_defenses", [])
        
        # Calculate attack stats
        attack_count = len(attacks_raw)
        attack_trophies = sum(attack.get("change", 0) for attack in attacks_raw)
        
        # Calculate defense stats
        defense_count = len(defenses_raw)
        defense_trophies = sum(defense.get("change", 0) for defense in defenses_raw)
        
        # Create embed for player day stats
        embed = nextcord.Embed(
            title=f"🏆 {player_name}'s Legend Day",
            description=f"Date: {date} | TH{townhall_level}",
            color=0xE1C16E  # Gold color
        )
        
        # Get current trophies
        current_trophies = "Unknown"
        if attacks_raw and "trophies" in attacks_raw[-1]:
            current_trophies = attacks_raw[-1]["trophies"]
        elif defenses_raw and "trophies" in defenses_raw[-1]:
            current_trophies = defenses_raw[-1]["trophies"]
        
        embed.add_field(name="Current Trophies", value=f"🏆 {current_trophies}", inline=True)
        
        # Add clan info if available
        clan = data.get("clan", {})
        if clan and clan.get("name"):
            embed.add_field(
                name="Clan", 
                value=f"{clan.get('name')}", 
                inline=True
            )

        # Add attack stats
        embed.add_field(
            name="Attacks",
            value=f"🗡️ **{attack_count}/8** attacks\n+{attack_trophies} trophies gained",
            inline=True
        )
        
        # Add defense stats
        embed.add_field(
            name="Defenses",
            value=f"🛡️ **{defense_count}** defenses\n{defense_trophies} trophies lost",
            inline=True
        )
        
        # Add net change
        net_change = attack_trophies + defense_trophies
        net_symbol = "+" if net_change > 0 else ""
        
        embed.add_field(
            name="Net Change",
            value=f"{net_symbol}{net_change} trophies",
            inline=True
        )
        
        # Add attack details if available
        if attacks_raw:
            attack_details = ""
            for i, attack in enumerate(attacks_raw, 1):
                opponent = attack.get("opponent_name", attack.get("opponentName", "Unknown"))
                change = attack.get("change", 0)
                attack_details += f"{i}. +{change} 🏆\n"
            
            embed.add_field(
                name="Attack Details",
                value=attack_details or "No attack details available",
                inline=False
            )
        
        # Add defense details if available
        if defenses_raw:
            defense_details = ""
            for i, defense in enumerate(defenses_raw, 1):
                opponent = defense.get("opponent_name", defense.get("opponentName", "Unknown"))
                change = defense.get("change", 0)
                defense_details += f"{i}. {change} 🏆\n"
            
            embed.add_field(
                name="Defense Details",
                value=defense_details or "No defense details available",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

def setup(bot):
    bot.add_cog(ClashLegendsStats(bot))
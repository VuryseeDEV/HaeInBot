import nextcord
from nextcord.ext import commands
import aiohttp
import random
import asyncio
import time
import sqlite3
import datetime
import re
import json
from typing import Optional, Tuple, List, Dict, Any

class AnimeCollect(commands.Cog):
    """Anime character collection system using AniList API - modern anime main characters"""

    def __init__(self, bot):
        self.bot = bot
        self.anilist_api_url = "https://graphql.anilist.co"
        self.roll_cooldown = 86400  
        self.roll_cost = 100
        self.max_collection = 100
        self.min_year = 2012  # Minimum year for anime
        
        # Connect to SQLite database
        self.conn = sqlite3.connect('anigame.db')
        self.cursor = self.conn.cursor()
        self.setup_database()

    def setup_database(self):
        """Create necessary tables if they don't exist - with server_id field for server separation"""
        # Define all tables in a single place with server_id fields
        tables = [
            '''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                server_id INTEGER,
                balance INTEGER DEFAULT 0,
                last_roll INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, server_id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS characters (
                character_id INTEGER,
                anime_id INTEGER,
                server_id INTEGER,
                name TEXT,
                anime TEXT,
                image_url TEXT,
                available INTEGER DEFAULT 1,
                role TEXT DEFAULT 'MAIN',
                PRIMARY KEY (character_id, server_id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                server_id INTEGER,
                character_id INTEGER,
                obtained_at INTEGER,
                FOREIGN KEY (user_id, server_id) REFERENCES users (user_id, server_id)
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                server_id INTEGER,
                character_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at INTEGER
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS trade_requests (
                trade_id INTEGER PRIMARY KEY,
                request_char_id INTEGER,
                FOREIGN KEY (trade_id) REFERENCES trades (trade_id)
            )
            '''
        ]
        
        # Execute all table creation statements
        for table in tables:
            self.cursor.execute(table)
        
        self.conn.commit()

    async def fetch_random_modern_anime(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch a random modern anime from AniList API"""
        # GraphQL query for random modern anime
        # Fetches popular anime from 2012 onwards
        query = """
        query ($page: Int, $perPage: Int, $minYear: FuzzyDateInt) {
          Page(page: $page, perPage: $perPage) {
            media(type: ANIME, sort: POPULARITY_DESC, startDate_greater: $minYear) {
              id
              title {
                romaji
                english
              }
              startDate {
                year
              }
              popularity
              averageScore
            }
          }
        }
        """
        
        # Get a random page to ensure variety
        page = random.randint(1, 20)
        
        variables = {
            "page": page,
            "perPage": 25,
            "minYear": self.min_year * 10000  # AniList format: YYYYMMDD (we only need year, so multiply by 10000)
        }
        
        try:
            async with session.post(
                self.anilist_api_url,
                json={"query": query, "variables": variables},
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if "errors" in data:
                        print(f"AniList API error: {data['errors']}")
                        return None
                    
                    anime_list = data.get("data", {}).get("Page", {}).get("media", [])
                    
                    if not anime_list:
                        print("No anime found")
                        return None
                    
                    # Pick a random anime from the results
                    return random.choice(anime_list)
                else:
                    # Handle API rate limiting
                    if response.status == 429:
                        print("Rate limited by AniList API, waiting...")
                        await asyncio.sleep(2)
                        return await self.fetch_random_modern_anime(session)
                    
                    print(f"AniList API returned status {response.status}")
                    response_text = await response.text()
                    print(f"Error details: {response_text[:200]}")
                    return None
                    
        except Exception as e:
            print(f"Error fetching random anime from AniList: {e}")
            return None

    async def fetch_anime_main_characters(self, session: aiohttp.ClientSession, anime_id: int) -> List[Dict[str, Any]]:
        """Fetch main characters for a specific anime from AniList API"""
        # GraphQL query for main anime characters
        query = """
        query ($animeId: Int) {
          Media(id: $animeId, type: ANIME) {
            title {
              romaji
              english
            }
            startDate {
              year
            }
            characters(role: MAIN, sort: FAVOURITES_DESC) {
              edges {
                node {
                  id
                  name {
                    full
                  }
                  image {
                    large
                  }
                }
                role
              }
            }
          }
        }
        """
        
        variables = {
            "animeId": anime_id
        }
        
        try:
            async with session.post(
                self.anilist_api_url,
                json={"query": query, "variables": variables},
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if "errors" in data:
                        print(f"AniList API error: {data['errors']}")
                        return []
                    
                    media_data = data.get("data", {}).get("Media", {})
                    title = media_data.get("title", {}).get("english") or media_data.get("title", {}).get("romaji", "Unknown Anime")
                    year = media_data.get("startDate", {}).get("year")
                    
                    characters_data = []
                    if "characters" in media_data and "edges" in media_data["characters"]:
                        for edge in media_data["characters"]["edges"]:
                            node = edge.get("node", {})
                            role = edge.get("role")
                            
                            if node and role == "MAIN":
                                characters_data.append({
                                    "id": node.get("id"),
                                    "name": node.get("name", {}).get("full", "Unknown"),
                                    "image_url": node.get("image", {}).get("large"),
                                    "anime_title": title,
                                    "anime_id": anime_id,
                                    "anime_year": year,
                                    "role": "MAIN"
                                })
                    
                    return characters_data
                else:
                    # Handle API rate limiting
                    if response.status == 429:
                        print("Rate limited by AniList API, waiting...")
                        await asyncio.sleep(2)
                        return await self.fetch_anime_main_characters(session, anime_id)
                    
                    print(f"AniList API returned status {response.status}")
                    response_text = await response.text()
                    print(f"Error details: {response_text[:200]}")
                    return []
                    
        except Exception as e:
            print(f"Error fetching characters from AniList: {e}")
            return []

    async def fetch_anime_character(self, session: aiohttp.ClientSession, server_id: int) -> Optional[tuple]:
        """Fetch a random main character from a random modern anime"""
        # First, get a random modern anime
        anime = await self.fetch_random_modern_anime(session)
        
        if not anime:
            print("Could not find a random modern anime")
            return None
        
        anime_id = anime.get("id")
        anime_title = anime.get("title", {}).get("english") or anime.get("title", {}).get("romaji", "Unknown Anime")
        anime_year = anime.get("startDate", {}).get("year")
        
        print(f"Selected anime: {anime_title} ({anime_year}) - ID: {anime_id}")
        
        # Check if we already have characters from this anime for this server
        self.cursor.execute(
            "SELECT COUNT(*) FROM characters WHERE anime_id = ? AND server_id = ?", 
            (anime_id, server_id)
        )
        existing_count = self.cursor.fetchone()[0]
        
        # If we already have characters from this anime in the database, try to get an available one
        if existing_count > 0:
            self.cursor.execute(
                "SELECT * FROM characters WHERE anime_id = ? AND server_id = ? AND available = 1 ORDER BY RANDOM() LIMIT 1", 
                (anime_id, server_id)
            )
            character = self.cursor.fetchone()
            
            # If we found an available character, return it
            if character:
                print(f"Found existing character: {character[3]}")
                return character
        
        # If we don't have any available characters from this anime (or none at all),
        # fetch character data from the API
        print(f"Fetching main characters for {anime_title}")
        characters = await self.fetch_anime_main_characters(session, anime_id)
        
        if not characters:
            print(f"No main characters found for anime ID {anime_id}")
            return None
        
        print(f"Found {len(characters)} main characters")
        
        # Shuffle characters to get random ones
        random.shuffle(characters)
        
        # Process characters
        for char_data in characters:
            try:
                char_id = char_data["id"]
                name = char_data["name"]
                image_url = char_data["image_url"]
                role = char_data["role"]
                
                # Format anime name with year
                anime_display = f"{anime_title} ({anime_year})" if anime_year else anime_title
                
                # Check if character already exists in this server
                self.cursor.execute(
                    "SELECT * FROM characters WHERE character_id = ? AND server_id = ?", 
                    (char_id, server_id)
                )
                existing_char = self.cursor.fetchone()
                
                # If character exists and is not available, skip
                if existing_char and existing_char[6] == 0:  # index 6 is 'available'
                    continue
                    
                # If character doesn't exist, add to database
                if not existing_char:
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO characters (character_id, anime_id, server_id, name, anime, image_url, available, role) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                        (char_id, anime_id, server_id, name, anime_display, image_url, role)
                    )
                    self.conn.commit()
                    
                    # Get the inserted character
                    self.cursor.execute(
                        "SELECT * FROM characters WHERE character_id = ? AND server_id = ?", 
                        (char_id, server_id)
                    )
                    char = self.cursor.fetchone()
                    print(f"Added new character to database: {name}")
                    return char
                else:
                    # If character exists and is available, return it
                    print(f"Found existing available character: {name}")
                    return existing_char
                    
            except Exception as e:
                print(f"Error processing character: {e}")
                continue
        
        # If we couldn't find any suitable characters, try another anime
        print("No suitable character found, trying another anime")
        return await self.fetch_anime_character(session, server_id)

    def ensure_user_exists(self, user_id: int, server_id: int):
        """Make sure the user exists in the database for the specific server"""
        self.cursor.execute("SELECT user_id FROM users WHERE user_id = ? AND server_id = ?", (user_id, server_id))
        if not self.cursor.fetchone():
            self.cursor.execute("INSERT INTO users (user_id, server_id, balance, last_roll) VALUES (?, ?, 0, 0)", (user_id, server_id))
            self.conn.commit()

    def get_user_balance(self, user_id: int, server_id: int) -> int:
        """Get a user's balance for the specific server"""
        self.ensure_user_exists(user_id, server_id)
        self.cursor.execute("SELECT balance FROM users WHERE user_id = ? AND server_id = ?", (user_id, server_id))
        return self.cursor.fetchone()[0]

    def update_user_balance(self, user_id: int, server_id: int, amount: int) -> int:
        """Update a user's balance for the specific server"""
        self.ensure_user_exists(user_id, server_id)
        new_balance = self.get_user_balance(user_id, server_id) + amount
        self.cursor.execute("UPDATE users SET balance = ? WHERE user_id = ? AND server_id = ?", (new_balance, user_id, server_id))
        self.conn.commit()
        return new_balance

    def get_collection_count(self, user_id: int, server_id: int) -> int:
        """Get the number of characters in a user's collection for the specific server"""
        self.cursor.execute("SELECT COUNT(*) FROM collections WHERE user_id = ? AND server_id = ?", (user_id, server_id))
        return self.cursor.fetchone()[0]

    async def add_character_to_collection(self, user_id: int, server_id: int, character: tuple):
        """Add a character to a user's collection and mark as unavailable"""
        char_id, anime_id, server_id_check, name, anime, image_url, available, role = character
        
        # Verify server_id matches
        if server_id != server_id_check:
            raise ValueError("Server ID mismatch when adding character to collection")
        
        # Mark character as unavailable
        self.cursor.execute("UPDATE characters SET available = 0 WHERE character_id = ? AND server_id = ?", (char_id, server_id))
        
        # Add to user's collection
        current_time = int(time.time())
        self.cursor.execute(
            "INSERT INTO collections (user_id, server_id, character_id, obtained_at) VALUES (?, ?, ?, ?)",
            (user_id, server_id, char_id, current_time)
        )
        
        # Update last roll time
        self.cursor.execute("UPDATE users SET last_roll = ? WHERE user_id = ? AND server_id = ?", (current_time, user_id, server_id))
        self.conn.commit()

    async def can_roll(self, user_id: int, server_id: int) -> bool:
        """Check if a user can roll (24-hour cooldown) for the specific server"""
        self.ensure_user_exists(user_id, server_id)
        self.cursor.execute("SELECT last_roll FROM users WHERE user_id = ? AND server_id = ?", (user_id, server_id))
        last_roll = self.cursor.fetchone()[0]
        current_time = int(time.time())
        return current_time - last_roll >= self.roll_cooldown

    def get_time_until_next_roll(self, user_id: int, server_id: int) -> str:
        """Get formatted time until next roll is available for the specific server"""
        self.cursor.execute("SELECT last_roll FROM users WHERE user_id = ? AND server_id = ?", (user_id, server_id))
        last_roll = self.cursor.fetchone()[0]
        time_left = self.roll_cooldown - (int(time.time()) - last_roll)
        if time_left <= 0:
            return "now"
        
        hours, remainder = divmod(time_left, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"

    async def get_character_embed(self, character: tuple) -> nextcord.Embed:
        """Create an embed for a character"""
        char_id, anime_id, server_id, name, anime, image_url, available, role = character
        
        embed = nextcord.Embed(
            title=f"{name}",
            color=0x1F85DE
        )
        embed.set_image(url=image_url)
        embed.add_field(name="Anime", value=anime, inline=True)
        embed.add_field(name="Role", value=role, inline=True)
        embed.add_field(name="Character ID", value=str(char_id), inline=True)
        embed.set_footer(text="Use this Character ID with /sell, /trade, or /gift commands")
        
        return embed

    def calculate_sell_price(self, anime: str) -> int:
        """Calculate sell price based on anime year"""
        try:
            # Try to extract year from anime name format "Anime Name (YYYY)"
            year_match = re.search(r'\((\d{4})\)', anime)
            if year_match:
                year = int(year_match.group(1))
                current_year = datetime.datetime.now().year
                
                # Newer anime characters are worth more
                years_old = current_year - year
                
                if years_old <= 1:  # Current year or last year
                    return random.randint(130, 150)
                elif years_old <= 3:  # Last 3 years
                    return random.randint(100, 130)
                elif years_old <= 5:  # Last 5 years
                    return random.randint(80, 100)
                else:  # Older than 5 years
                    return random.randint(50, 80)
            else:
                # Default random price if year not found
                return random.randint(50, 150)
        except Exception:
            # Fallback to random pricing
            return random.randint(50, 150)

    # Commands
    @nextcord.slash_command(name="roll", description="Roll for a random anime character (once every 24 hours)")
    async def roll(self, interaction: nextcord.Interaction):
        """Roll for a random anime character (once every 24 hours)"""
        user_id = interaction.user.id
        server_id = interaction.guild_id
        self.ensure_user_exists(user_id, server_id)
        
        # Check if collection is full
        if self.get_collection_count(user_id, server_id) >= self.max_collection:
            await interaction.response.send_message("Your collection is full! Sell some characters before rolling again.")
            return
        
        # Check cooldown
        if not await self.can_roll(user_id, server_id):
            time_left = self.get_time_until_next_roll(user_id, server_id)
            await interaction.response.send_message(
                f"You can roll again in {time_left}. Or use `/buyroll` to roll immediately!")
            return
        
        # Make sure we respond immediately to avoid timeout
        await interaction.response.send_message("Rolling for a character... please wait!")
        
        try:
            # Fetch a random character (on-demand fetching)
            async with aiohttp.ClientSession() as session:
                character = await self.fetch_anime_character(session, server_id)
                
                if not character:
                    await interaction.channel.send("No suitable characters found. Please try again later.")
                    return
                
                await self.add_character_to_collection(user_id, server_id, character)
                
                embed = await self.get_character_embed(character)
                await interaction.channel.send(f"{interaction.user.mention} rolled and got:", embed=embed)
        except Exception as e:
            await interaction.channel.send(f"An error occurred: {str(e)}")

    @nextcord.slash_command(name="buyroll", description="Buy a roll for credits")
    async def buyroll(self, interaction: nextcord.Interaction):
        """Buy a roll for 100 credits"""
        user_id = interaction.user.id
        server_id = interaction.guild_id
        self.ensure_user_exists(user_id, server_id)
        
        # Check if collection is full
        if self.get_collection_count(user_id, server_id) >= self.max_collection:
            await interaction.response.send_message("Your collection is full! Sell some characters before rolling again.")
            return
        
        # Check if user has enough credits
        balance = self.get_user_balance(user_id, server_id)
        if balance < self.roll_cost:
            await interaction.response.send_message(f"You don't have enough credits! You need {self.roll_cost} credits, but you only have {balance}.")
            return
        
        # Make sure we respond immediately to avoid timeout
        await interaction.response.send_message(f"Spending {self.roll_cost} credits to roll for a character... please wait!")
        
        try:
            # Deduct credits
            self.update_user_balance(user_id, server_id, -self.roll_cost)
            
            # Fetch a random character (on-demand fetching)
            async with aiohttp.ClientSession() as session:
                character = await self.fetch_anime_character(session, server_id)
                
                if not character:
                    # Refund if no character available
                    self.update_user_balance(user_id, server_id, self.roll_cost)
                    await interaction.channel.send("No suitable characters found. Your credits have been refunded.")
                    return
                
                await self.add_character_to_collection(user_id, server_id, character)
                
                embed = await self.get_character_embed(character)
                await interaction.channel.send(f"{interaction.user.mention} spent {self.roll_cost} credits and got:", embed=embed)
        except Exception as e:
            # Refund on error
            self.update_user_balance(user_id, server_id, self.roll_cost)
            await interaction.channel.send(f"An error occurred: {str(e)}. Your credits have been refunded.")

    @nextcord.slash_command(name="collection", description="View your or someone else's anime character collection")
    async def collection(
        self, 
        interaction: nextcord.Interaction, 
        user: Optional[nextcord.Member] = None, 
        page: int = 1
    ):
        """View a user's collection with character thumbnails"""
        server_id = interaction.guild_id
        target_user = user or interaction.user
        target_id = target_user.id
        self.ensure_user_exists(target_id, server_id)
        
        await interaction.response.defer()
        
        # Get collection count
        collection_count = self.get_collection_count(target_id, server_id)
        if collection_count == 0:
            await interaction.followup.send(f"{target_user.display_name} doesn't have any characters in their collection yet!")
            return
        
        # Calculate pagination
        items_per_page = 5
        max_pages = (collection_count + items_per_page - 1) // items_per_page
        
        if page < 1 or page > max_pages:
            page = 1
        
        offset = (page - 1) * items_per_page
        
        # Get character data for the page
        self.cursor.execute("""
            SELECT characters.character_id, characters.anime_id, characters.server_id, characters.name, 
                characters.anime, characters.image_url, characters.available, characters.role, collections.id
            FROM collections
            JOIN characters ON collections.character_id = characters.character_id AND collections.server_id = characters.server_id
            WHERE collections.user_id = ? AND collections.server_id = ?
            ORDER BY collections.obtained_at DESC
            LIMIT ? OFFSET ?
        """, (target_id, server_id, items_per_page, offset))
        
        characters = self.cursor.fetchall()
        
        # Create embed
        embed = nextcord.Embed(
            title=f"{target_user.display_name}'s Anime Collection",
            description=f"Showing page {page}/{max_pages} ({collection_count}/{self.max_collection} characters)",
            color=0x1F85DE
        )

        # Add balance info in the footer
        balance = self.get_user_balance(target_id, server_id)
        embed.set_footer(text=f"Balance: {balance} credits | Use /roll or /buyroll to get more characters!")
        
        # Add each character to the embed with thumbnails
        for idx, character in enumerate(characters):
            char_id, anime_id, char_server_id, name, anime, image_url, available, role, collection_id = character
            
            # Set character thumbnail to embed
            if idx == 0:  # Set the first character as the main thumbnail
                embed.set_thumbnail(url=image_url)
            
            # Add character info to embed
            embed.add_field(
                name=f"{name} (ID: {char_id})",
                value=f"From: {anime}\nRole: {role}\nCollection ID: {collection_id}\n[View Image]({image_url})",
                inline=False
            )
        
        # Navigation buttons
        view = nextcord.ui.View(timeout=60)
        
        # Add prev button if not on first page
        if page > 1:
            prev_button = nextcord.ui.Button(label="Previous Page", style=nextcord.ButtonStyle.gray)
            
            async def prev_callback(button_interaction):
                if button_interaction.user.id != interaction.user.id:
                    return
                await self.collection(button_interaction, target_user, page - 1)
                
            prev_button.callback = prev_callback
            view.add_item(prev_button)
        
        # Add next button if not on last page
        if page < max_pages:
            next_button = nextcord.ui.Button(label="Next Page", style=nextcord.ButtonStyle.gray)
            
            async def next_callback(button_interaction):
                if button_interaction.user.id != interaction.user.id:
                    return
                await self.collection(button_interaction, target_user, page + 1)
                
            next_button.callback = next_callback
            view.add_item(next_button)
        
        await interaction.followup.send(embed=embed, view=view)

    @nextcord.slash_command(name="sell", description="Sell a character from your collection")
    async def sell(
        self,
        interaction: nextcord.Interaction,
        character_id: int = nextcord.SlashOption(
            name="character_id",
            description="ID of the character you want to sell",
            required=True
        )
    ):
        """Sell a specific character from your collection for credits"""
        user_id = interaction.user.id
        server_id = interaction.guild_id
        self.ensure_user_exists(user_id, server_id)
        
        # Check if the user owns this character
        self.cursor.execute("""
            SELECT collections.id, characters.character_id, characters.name, characters.anime
            FROM collections
            JOIN characters ON collections.character_id = characters.character_id AND collections.server_id = characters.server_id
            WHERE collections.user_id = ? AND collections.server_id = ? AND characters.character_id = ?
        """, (user_id, server_id, character_id))
        
        character = self.cursor.fetchone()
        
        if not character:
            await interaction.response.send_message("You don't own a character with that ID!", ephemeral=True)
            return
        
        collection_id, char_id, char_name, anime = character
        
        # Calculate sell price based on anime year
        sell_price = self.calculate_sell_price(anime)
        
        # Mark character as available again
        self.cursor.execute("UPDATE characters SET available = 1 WHERE character_id = ? AND server_id = ?", (char_id, server_id))
        
        # Remove character from collection
        self.cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        
        # Add credits to user
        new_balance = self.update_user_balance(user_id, server_id, sell_price)
        
        self.conn.commit()
        
        await interaction.response.send_message(
            f"You sold {char_name} for {sell_price} credits! Your new balance is {new_balance} credits."
        )

    @nextcord.slash_command(name="sellall", description="Sell all characters in your collection")
    async def sellall(self, interaction: nextcord.Interaction):
        """Sell all characters in your collection for credits"""
        user_id = interaction.user.id
        server_id = interaction.guild_id
        self.ensure_user_exists(user_id, server_id)
        
        # Get all characters in the user's collection
        self.cursor.execute("""
            SELECT collections.id, characters.character_id, characters.name, characters.anime
            FROM collections
            JOIN characters ON collections.character_id = characters.character_id AND collections.server_id = characters.server_id
            WHERE collections.user_id = ? AND collections.server_id = ?
        """, (user_id, server_id))
        
        characters = self.cursor.fetchall()
        
        if not characters:
            await interaction.response.send_message("You don't have any characters to sell!")
            return
        
        # Ask for confirmation since this is a significant action
        character_count = len(characters)
        
        embed = nextcord.Embed(
            title=f"Sell All Characters?",
            description=f"Are you sure you want to sell all {character_count} characters in your collection? This action cannot be undone!",
            color=0xE74C3C
        )
        
        confirm_view = nextcord.ui.View(timeout=30)
        confirm_button = nextcord.ui.Button(label="Confirm", style=nextcord.ButtonStyle.red)
        cancel_button = nextcord.ui.Button(label="Cancel", style=nextcord.ButtonStyle.gray)
        
        async def confirm_callback(confirm_interaction):
            if confirm_interaction.user.id != user_id:
                return
                
            # Calculate prices for all characters
            total_credits = 0
            for collection_id, char_id, char_name, anime in characters:
                # Calculate sell price based on anime year
                sell_price = self.calculate_sell_price(anime)
                total_credits += sell_price
                
                # Mark character as available again
                self.cursor.execute("UPDATE characters SET available = 1 WHERE character_id = ? AND server_id = ?", (char_id, server_id))
            
            # Remove all characters from collection
            self.cursor.execute("DELETE FROM collections WHERE user_id = ? AND server_id = ?", (user_id, server_id))
            
            # Add credits to user
            new_balance = self.update_user_balance(user_id, server_id, total_credits)
            
            self.conn.commit()
            
            await interaction.edit_original_message(
                content=f"Sold {character_count} characters for a total of {total_credits} credits! Your new balance is {new_balance} credits.",
                embed=None,
                view=None
            )
            
        async def cancel_callback(cancel_interaction):
            if cancel_interaction.user.id != user_id:
                return
                
            await interaction.edit_original_message(
                content="Operation cancelled. Your collection is safe!",
                embed=None,
                view=None
            )
            
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=confirm_view)

    @nextcord.slash_command(name="trade", description="Offer to trade a character with another user")
    async def trade(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = nextcord.SlashOption(
            name="user",
            description="User to trade with",
            required=True
        ),
        offer_character_id: int = nextcord.SlashOption(
            name="offer",
            description="ID of the character you're offering",
            required=True
        ),
        request_character_id: int = nextcord.SlashOption(
            name="request",
            description="ID of the character you're requesting (0 for any character)",
            required=False,
            default=0
        )
    ):
        """Offer to trade a character with another user"""
        sender_id = interaction.user.id
        receiver_id = user.id
        server_id = interaction.guild_id
        
        # Check if trying to trade with self
        if sender_id == receiver_id:
            await interaction.response.send_message("You can't trade with yourself!", ephemeral=True)
            return
        
        # Check if sender owns the offered character
        self.cursor.execute("""
            SELECT characters.character_id, characters.name, characters.image_url
            FROM collections
            JOIN characters ON collections.character_id = characters.character_id AND collections.server_id = characters.server_id
            WHERE collections.user_id = ? AND collections.server_id = ? AND characters.character_id = ?
        """, (sender_id, server_id, offer_character_id))
        
        offer_character = self.cursor.fetchone()
        
        if not offer_character:
            await interaction.response.send_message("You don't own the character you're trying to offer!", ephemeral=True)
            return
        
        offer_char_id, offer_char_name, offer_image_url = offer_character
        
        # Check if receiver owns the requested character (if specified)
        request_char_name = "any character"
        request_image_url = None
        
        if request_character_id > 0:
            self.cursor.execute("""
                SELECT characters.character_id, characters.name, characters.image_url
                FROM collections
                JOIN characters ON collections.character_id = characters.character_id AND collections.server_id = characters.server_id
                WHERE collections.user_id = ? AND collections.server_id = ? AND characters.character_id = ?
            """, (receiver_id, server_id, request_character_id))
            
            request_character = self.cursor.fetchone()
            
            if not request_character:
                await interaction.response.send_message(f"{user.display_name} doesn't own the character you're requesting!", ephemeral=True)
                return
            
            request_char_id, request_char_name, request_image_url = request_character
        
        # Create a trade entry
        current_time = int(time.time())
        self.cursor.execute(
            "INSERT INTO trades (sender_id, receiver_id, server_id, character_id, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (sender_id, receiver_id, server_id, offer_char_id, current_time)
        )
        self.conn.commit()
        trade_id = self.cursor.lastrowid
        
        # Store request character ID if specified
        if request_character_id > 0:
            self.cursor.execute(
                "INSERT INTO trade_requests (trade_id, request_char_id) VALUES (?, ?)",
                (trade_id, request_character_id)
            )
            self.conn.commit()
        
        # Create trade embed
        embed = nextcord.Embed(
            title="Trade Offer",
            description=f"{interaction.user.display_name} wants to trade with you!",
            color=0x1F85DE
        )
        
        embed.add_field(
            name="Offering",
            value=f"{offer_char_name} (ID: {offer_char_id})",
            inline=True
        )
        
        embed.add_field(
            name="Requesting",
            value=f"{request_char_name} {f'(ID: {request_character_id})' if request_character_id > 0 else ''}",
            inline=True
        )
        
        embed.set_thumbnail(url=offer_image_url)
        embed.set_footer(text=f"Trade ID: {trade_id}")
        
        # Create buttons
        view = nextcord.ui.View(timeout=86400)  # 24 hour timeout
        
        accept_button = nextcord.ui.Button(
            label="Accept Trade",
            style=nextcord.ButtonStyle.green
        )
        
        decline_button = nextcord.ui.Button(
            label="Decline Trade",
            style=nextcord.ButtonStyle.red
        )
        
        async def accept_callback(button_interaction):
            # Ensure only the receiver can accept
            if button_interaction.user.id != receiver_id:
                await button_interaction.response.send_message("This trade isn't for you to accept!", ephemeral=True)
                return
            
            # Get trade details again to make sure it's still valid
            self.cursor.execute("SELECT * FROM trades WHERE trade_id = ? AND status = 'pending'", (trade_id,))
            trade = self.cursor.fetchone()
            
            if not trade:
                await button_interaction.response.send_message("This trade is no longer valid!", ephemeral=True)
                return
                
            # Verify server_id matches current server
            if trade[3] != server_id:  # index 3 is server_id
                await button_interaction.response.send_message("This trade is from a different server!", ephemeral=True)
                return
                
            # Get the offered character ID
            offered_char_id = trade[4]  # index 4 is character_id
            
            # Get the requested character ID if it exists
            self.cursor.execute("SELECT request_char_id FROM trade_requests WHERE trade_id = ?", (trade_id,))
            request_result = self.cursor.fetchone()
            requested_char_id = request_result[0] if request_result else 0
            
            # Verify both users still own their respective characters
            self.cursor.execute("""
                SELECT character_id FROM collections 
                WHERE user_id = ? AND server_id = ? AND character_id = ?
            """, (sender_id, server_id, offered_char_id))
            
            if not self.cursor.fetchone():
                await button_interaction.response.send_message(
                    f"{interaction.user.display_name} no longer owns the offered character!",
                    ephemeral=True
                )
                return
            
            if requested_char_id > 0:
                self.cursor.execute("""
                    SELECT character_id FROM collections 
                    WHERE user_id = ? AND server_id = ? AND character_id = ?
                """, (receiver_id, server_id, requested_char_id))
                
                if not self.cursor.fetchone():
                    await button_interaction.response.send_message(
                        "You no longer own the requested character!",
                        ephemeral=True
                    )
                    return
            
            # If specific character requested, perform swap
            if requested_char_id > 0:
                # Update collections for offered character
                self.cursor.execute("""
                    UPDATE collections 
                    SET user_id = ? 
                    WHERE user_id = ? AND server_id = ? AND character_id = ?
                """, (receiver_id, sender_id, server_id, offered_char_id))
                
                # Update collections for requested character
                self.cursor.execute("""
                    UPDATE collections 
                    SET user_id = ? 
                    WHERE user_id = ? AND server_id = ? AND character_id = ?
                """, (sender_id, receiver_id, server_id, requested_char_id))
            else:
                # If no specific character requested, get a random character from receiver
                self.cursor.execute("""
                    SELECT character_id, 
                    (SELECT name FROM characters WHERE character_id = collections.character_id AND server_id = collections.server_id) as name
                    FROM collections
                    WHERE user_id = ? AND server_id = ?
                    ORDER BY RANDOM()
                    LIMIT 1
                """, (receiver_id, server_id))
                
                random_char = self.cursor.fetchone()
                
                if not random_char:
                    await button_interaction.response.send_message(
                        f"{user.display_name} doesn't have any characters to trade!",
                        ephemeral=True
                    )
                    return
                
                random_char_id, random_char_name = random_char
                
                # Update collections for offered character
                self.cursor.execute("""
                    UPDATE collections 
                    SET user_id = ? 
                    WHERE user_id = ? AND server_id = ? AND character_id = ?
                """, (receiver_id, sender_id, server_id, offered_char_id))
                
                # Update collections for random character
                self.cursor.execute("""
                    UPDATE collections 
                    SET user_id = ? 
                    WHERE user_id = ? AND server_id = ? AND character_id = ?
                """, (sender_id, receiver_id, server_id, random_char_id))
                
                # Update request_char_name for notification
                request_char_name = f"{random_char_name} (ID: {random_char_id})"
                requested_char_id = random_char_id
            
            # Update trade status
            self.cursor.execute("UPDATE trades SET status = 'completed' WHERE trade_id = ?", (trade_id,))
            self.conn.commit()
            
            # Get character names for notification
            self.cursor.execute("SELECT name FROM characters WHERE character_id = ? AND server_id = ?", (offered_char_id, server_id))
            offer_name_result = self.cursor.fetchone()
            offer_char_name = offer_name_result[0] if offer_name_result else f"Character #{offered_char_id}"
            
            self.cursor.execute("SELECT name FROM characters WHERE character_id = ? AND server_id = ?", (requested_char_id, server_id))
            request_name_result = self.cursor.fetchone()
            request_char_name = request_name_result[0] if request_name_result else f"Character #{requested_char_id}"
            
            # Notify both users
            await button_interaction.response.send_message(
                f"Trade completed! {interaction.user.display_name} received {request_char_name} and {user.display_name} received {offer_char_name}.",
                ephemeral=False
            )
            
            # Update the original message to show the trade is completed
            embed.title = "Trade Completed"
            embed.color = 0x00FF00
            await button_interaction.message.edit(embed=embed, view=None)
        
        async def decline_callback(button_interaction):
            # Ensure only the receiver can decline
            if button_interaction.user.id != receiver_id:
                await button_interaction.response.send_message("This trade isn't for you to decline!", ephemeral=True)
                return
            
            # Update trade status
            self.cursor.execute("UPDATE trades SET status = 'declined' WHERE trade_id = ?", (trade_id,))
            self.conn.commit()
            
            # Notify both users
            await button_interaction.response.send_message(
                f"{user.display_name} declined the trade offer from {interaction.user.display_name}.",
                ephemeral=False
            )
            
            # Update the original message to show the trade is declined
            embed.title = "Trade Declined"
            embed.color = 0xFF0000
            await button_interaction.message.edit(embed=embed, view=None)
        
        accept_button.callback = accept_callback
        decline_button.callback = decline_callback
        
        view.add_item(accept_button)
        view.add_item(decline_button)
        
        # Send the trade offer
        await interaction.response.send_message(f"{user.mention}, you have a trade offer from {interaction.user.display_name}!", embed=embed, view=view)

    @nextcord.slash_command(name="delete_data", description="Delete anime collection data for this server (Admin only)")
    async def delete_data(self, interaction: nextcord.Interaction, confirm: str = nextcord.SlashOption(
        name="confirm",
        description="Type 'confirm' to delete data",
        required=True
    )):
        """Delete anime collection data for this server"""
        # Check for admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("This command requires administrator permissions!", ephemeral=True)
            return
            
        server_id = interaction.guild_id
        
        # Require confirmation text
        if confirm.lower() != "confirm":
            await interaction.response.send_message("Please type 'confirm' to confirm data deletion.", ephemeral=True)
            return
            
        # Create a second confirmation since this is destructive
        embed = nextcord.Embed(
            title=f"⚠️ DANGER: Delete ALL Game Data ⚠️",
            description=f"This will delete ALL anime collection data for this server. Users will lose their collections and credits. This action CANNOT be undone!",
            color=0xFF0000
        )
        
        confirm_view = nextcord.ui.View(timeout=30)
        confirm_button = nextcord.ui.Button(label="Yes, Delete Everything", style=nextcord.ButtonStyle.danger)
        cancel_button = nextcord.ui.Button(label="Cancel", style=nextcord.ButtonStyle.gray)
        
        async def confirm_callback(confirm_interaction):
            if confirm_interaction.user.id != interaction.user.id:
                return
                
            # Delete data for this server only
            try:
                # Delete collections first (foreign key constraints)
                self.cursor.execute("DELETE FROM collections WHERE server_id = ?", (server_id,))
                
                # Delete characters
                self.cursor.execute("DELETE FROM characters WHERE server_id = ?", (server_id,))
                
                # Delete trades (need to find trades for this server first)
                self.cursor.execute("SELECT trade_id FROM trades WHERE server_id = ?", (server_id,))
                trade_ids = [row[0] for row in self.cursor.fetchall()]
                
                if trade_ids:
                    # Delete trade requests for these trades
                    self.cursor.execute(f"DELETE FROM trade_requests WHERE trade_id IN ({','.join(['?']*len(trade_ids))})", trade_ids)
                
                # Delete trades
                self.cursor.execute("DELETE FROM trades WHERE server_id = ?", (server_id,))
                
                # Delete users
                self.cursor.execute("DELETE FROM users WHERE server_id = ?", (server_id,))
                
                self.conn.commit()
                
                await interaction.edit_original_message(
                    content=f"✅ Successfully deleted all anime collection data for this server.",
                    embed=None,
                    view=None
                )
            except Exception as e:
                await interaction.edit_original_message(
                    content=f"❌ Error deleting data: {str(e)}",
                    embed=None,
                    view=None
                )
            
        async def cancel_callback(cancel_interaction):
            if cancel_interaction.user.id != interaction.user.id:
                return
                
            await interaction.edit_original_message(
                content="Operation cancelled. Data was not deleted.",
                embed=None,
                view=None
            )
            
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=confirm_view)

    @nextcord.slash_command(name="search", description="Search for available characters")
    async def search(
        self, 
        interaction: nextcord.Interaction,
        anime_name: str = nextcord.SlashOption(
            name="anime",
            description="Name of anime to search for characters",
            required=False
        ),
        character_name: str = nextcord.SlashOption(
            name="character",
            description="Name of character to search for",
            required=False
        )
    ):
        """Search for available characters"""
        server_id = interaction.guild_id
        
        # Build the query based on provided parameters
        query = "SELECT * FROM characters WHERE available = 1 AND server_id = ?"
        params = [server_id]
        
        if anime_name:
            query += " AND anime LIKE ?"
            params.append(f"%{anime_name}%")
            
        if character_name:
            query += " AND name LIKE ?"
            params.append(f"%{character_name}%")
            
        query += " LIMIT 10"  # Limit results
        
        # Execute the query
        self.cursor.execute(query, params)
        characters = self.cursor.fetchall()
        
        if not characters:
            await interaction.response.send_message("No available characters found matching your search criteria.")
            return
        
        # Create embed with results
        embed = nextcord.Embed(
            title="Search Results",
            description=f"Found {len(characters)} available characters",
            color=0x1F85DE
        )
        
        for character in characters:
            char_id, anime_id, char_server_id, name, anime, image_url, available, role = character
            embed.add_field(
                name=f"{name} (ID: {char_id})",
                value=f"From: {anime}\nRole: {role}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

    @nextcord.slash_command(name="addbal", description="Add credits to a user's balance (Server owner only)")
    async def addbal(
        self, 
        interaction: nextcord.Interaction,
        user: nextcord.Member = nextcord.SlashOption(
            name="user",
            description="User to add credits to",
            required=True
        ),
        amount: int = nextcord.SlashOption(
            name="amount",
            description="Amount of credits to add",
            required=True,
            min_value=1,
            max_value=10000
        )
    ):
        """Add credits to a user's balance (Server owner only)"""
        server_id = interaction.guild_id
        
        #Check if the command user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("This command can only be used by the server owner!", ephemeral=True)
            return
        
        #Ensure the user exists in the database
        self.ensure_user_exists(user.id, server_id)
        
        #gives credits to user
        previous_balance = self.get_user_balance(user.id, server_id)
        new_balance = self.update_user_balance(user.id, server_id, amount)
        
        await interaction.response.send_message(
            f"Added {amount} credits to {user.mention}'s balance!\n"
            f"Previous balance: {previous_balance} credits\n"
            f"New balance: {new_balance} credits"
        )
    @nextcord.slash_command(name="pay", description="Give credits to another user")
    async def pay(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = nextcord.SlashOption(
            name="user",
            description="User to send credits to",
            required=True
        ),
        amount: int = nextcord.SlashOption(
            name="amount",
            description="Amount of credits to give",
            required=True,
            min_value=1
        )
    ):
        """Give credits to another user"""
        sender_id = interaction.user.id
        receiver_id = user.id
        server_id = interaction.guild_id
        
        # Check if trying to pay self
        if sender_id == receiver_id:
            await interaction.response.send_message("You can't pay yourself!", ephemeral=True)
            return
        
        # Ensure both users exist in the database
        self.ensure_user_exists(sender_id, server_id)
        self.ensure_user_exists(receiver_id, server_id)
        
        # Check if sender has enough credits
        sender_balance = self.get_user_balance(sender_id, server_id)
        if sender_balance < amount:
            await interaction.response.send_message(
                f"You don't have enough credits! Your balance: {sender_balance} credits.",
                ephemeral=True
            )
            return
        
        # Create confirmation embed
        embed = nextcord.Embed(
            title="Payment Confirmation",
            description=f"Are you sure you want to send {amount} credits to {user.display_name}?",
            color=0x1F85DE
        )
        embed.set_footer(text=f"Your current balance: {sender_balance} credits")
        
        # Create confirmation buttons
        view = nextcord.ui.View(timeout=30)
        confirm_button = nextcord.ui.Button(label="Confirm Payment", style=nextcord.ButtonStyle.green)
        cancel_button = nextcord.ui.Button(label="Cancel", style=nextcord.ButtonStyle.red)
        
        async def confirm_callback(confirm_interaction):
            if confirm_interaction.user.id != sender_id:
                return
            
            # Deduct from sender
            new_sender_balance = self.update_user_balance(sender_id, server_id, -amount)
            
            # Add to receiver
            new_receiver_balance = self.update_user_balance(receiver_id, server_id, amount)
            
            # Create payment success embed
            success_embed = nextcord.Embed(
                title="Payment Sent!",
                description=f"{interaction.user.display_name} has sent {amount} credits to {user.display_name}!",
                color=0x00FF00
            )
            success_embed.add_field(
                name=f"{interaction.user.display_name}'s Balance",
                value=f"{new_sender_balance} credits",
                inline=True
            )
            success_embed.add_field(
                name=f"{user.display_name}'s Balance",
                value=f"{new_receiver_balance} credits",
                inline=True
            )
            
            await interaction.edit_original_message(
                content=None,
                embed=success_embed,
                view=None
            )
            
        async def cancel_callback(cancel_interaction):
            if cancel_interaction.user.id != sender_id:
                return
            
            await interaction.edit_original_message(
                content="Payment cancelled.",
                embed=None,
                view=None
            )
            
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        
        view.add_item(confirm_button)
        view.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=view)
    @nextcord.slash_command(name="gift", description="Gift a character from your collection to another user")
    async def gift(
        self,
        interaction: nextcord.Interaction,
        user: nextcord.Member = nextcord.SlashOption(
            name="user",
            description="User to gift the character to",
            required=True
        ),
        character_id: int = nextcord.SlashOption(
            name="character_id",
            description="ID of the character you want to gift",
            required=True
        )
    ):
        """Gift a character from your collection to another user"""
        sender_id = interaction.user.id
        receiver_id = user.id
        server_id = interaction.guild_id
        
        # Check if trying to gift to self
        if sender_id == receiver_id:
            await interaction.response.send_message("You can't gift a character to yourself!", ephemeral=True)
            return
        
        # Check if sender owns the character
        self.cursor.execute("""
            SELECT collections.id, characters.character_id, characters.name, characters.image_url, characters.anime
            FROM collections
            JOIN characters ON collections.character_id = characters.character_id AND collections.server_id = characters.server_id
            WHERE collections.user_id = ? AND collections.server_id = ? AND characters.character_id = ?
        """, (sender_id, server_id, character_id))
        
        character = self.cursor.fetchone()
        
        if not character:
            await interaction.response.send_message("You don't own a character with that ID!", ephemeral=True)
            return
        
        collection_id, char_id, char_name, char_image, anime_name = character
        
        # Check if receiver's collection is full
        if self.get_collection_count(receiver_id, server_id) >= self.max_collection:
            await interaction.response.send_message(
                f"{user.display_name}'s collection is full! They need to make room before receiving gifts.",
                ephemeral=True
            )
            return
        
        # Create confirmation embed with character image
        embed = nextcord.Embed(
            title=f"Gift Character Confirmation",
            description=f"Are you sure you want to gift {char_name} from {anime_name} to {user.display_name}?",
            color=0x1F85DE
        )
        embed.set_thumbnail(url=char_image)
        
        # Create confirmation buttons
        view = nextcord.ui.View(timeout=30)
        confirm_button = nextcord.ui.Button(label="Confirm Gift", style=nextcord.ButtonStyle.green)
        cancel_button = nextcord.ui.Button(label="Cancel", style=nextcord.ButtonStyle.red)
        
        async def confirm_callback(confirm_interaction):
            if confirm_interaction.user.id != sender_id:
                return
            
            # Transfer character ownership
            self.cursor.execute(
                "UPDATE collections SET user_id = ? WHERE id = ?",
                (receiver_id, collection_id)
            )
            self.conn.commit()
            
            # Create gift success embed
            success_embed = nextcord.Embed(
                title="Gift Sent!",
                description=f"{interaction.user.display_name} has gifted {char_name} to {user.display_name}!",
                color=0x00FF00
            )
            success_embed.set_thumbnail(url=char_image)
            
            await interaction.edit_original_message(
                content=None,
                embed=success_embed,
                view=None
            )
            
        async def cancel_callback(cancel_interaction):
            if cancel_interaction.user.id != sender_id:
                return
            
            await interaction.edit_original_message(
                content="Gift cancelled.",
                embed=None,
                view=None
            )
            
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        
        view.add_item(confirm_button)
        view.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=view)

def setup(bot):
    bot.add_cog(AnimeCollect(bot))
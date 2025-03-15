import nextcord
from nextcord import SlashOption, Colour
from nextcord.ext import commands, tasks
import sqlite3
import os
import time
import asyncio

class BoosterPerks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_file = "custom_roles.db"
        self._setup_database()
        # Default booster role name, can be changed with set_booster_role command
        self.booster_role_name = "Server Booster"
        self._load_config()
        self.temp_channels = {}  # Dictionary to track temporary channels and their creation time
        self.check_empty_channels.start()  # Start background task to check channels
        
    def _setup_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_roles (
            user_id TEXT PRIMARY KEY,
            role_id TEXT,
            guild_id TEXT,
            active INTEGER DEFAULT 1
        )
        ''')
        
        # Check if config table exists, if not create it
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            guild_id TEXT PRIMARY KEY,
            booster_role_name TEXT
        )
        ''')
        
        # Check if 'active' column exists in custom_roles table
        cursor.execute("PRAGMA table_info(custom_roles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # If 'active' column doesn't exist, add it
        if 'active' not in columns:
            cursor.execute("ALTER TABLE custom_roles ADD COLUMN active INTEGER DEFAULT 1")
            print("Added 'active' column to custom_roles table")
        
        conn.commit()
        conn.close()
        
    def _load_config(self):
        """Load booster role name from config if it exists."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT booster_role_name FROM config WHERE guild_id = ?", 
                      (str(self.bot.guilds[0].id) if self.bot.guilds else "0",))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            self.booster_role_name = result[0]
        
    def _save_config(self, guild_id, booster_role_name):
        """Save booster role name to config."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO config (guild_id, booster_role_name) VALUES (?, ?)",
            (str(guild_id), booster_role_name)
        )
        conn.commit()
        conn.close()
        self.booster_role_name = booster_role_name
        
    def _get_custom_role(self, user_id, guild_id):
        """Get the custom role ID for a user in a guild."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role_id, active FROM custom_roles WHERE user_id = ? AND guild_id = ?", 
            (str(user_id), str(guild_id))
        )
        result = cursor.fetchone()
        conn.close()
        return (int(result[0]), bool(result[1])) if result else (None, False)
        
    def _save_custom_role(self, user_id, role_id, guild_id, active=True):
        """Save a custom role to the database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO custom_roles (user_id, role_id, guild_id, active) VALUES (?, ?, ?, ?)",
            (str(user_id), str(role_id), str(guild_id), 1 if active else 0)
        )
        conn.commit()
        conn.close()
        
    def _update_role_status(self, user_id, guild_id, active):
        """Update the active status of a role."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE custom_roles SET active = ? WHERE user_id = ? AND guild_id = ?",
            (1 if active else 0, str(user_id), str(guild_id))
        )
        conn.commit()
        conn.close()
        
    def _delete_custom_role(self, user_id, guild_id):
        """Delete a custom role from the database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM custom_roles WHERE user_id = ? AND guild_id = ?",
            (str(user_id), str(guild_id))
        )
        conn.commit()
        conn.close()

    def _is_booster(self, member, guild):
        """Check if a member is a server booster."""
        booster_role = nextcord.utils.get(guild.roles, name=self.booster_role_name)
        return booster_role in member.roles if booster_role else False

    @nextcord.slash_command()
    async def booster(self, interaction: nextcord.Interaction):
        """Commands for server boosters."""
        pass

    @booster.subcommand()
    async def claim(
        self,
        interaction: nextcord.Interaction,
        role_name: str = SlashOption(description="Name of the role"),
        hex_code: str = SlashOption(description="Hex code for the role color (e.g., #ff5733)"),
        bypass_check: bool = SlashOption(description="Admin-only: Bypass booster check", required=False, default=False)
    ):
        """Claim a custom role if you are a server booster."""
        member = interaction.user
        guild = interaction.guild

        # Check if the user is a server booster by role
        is_booster = self._is_booster(member, guild)
        is_admin = member.guild_permissions.administrator
        
        # For debugging - allow admins to bypass the booster check
        if not is_booster and not (bypass_check and is_admin):
            booster_role = nextcord.utils.get(guild.roles, name=self.booster_role_name)
            await interaction.response.send_message(
                f"You must be a server booster to use this command! " 
                f"Looking for role: '{self.booster_role_name}' which {'' if booster_role else 'does not exist'}."
                f"\nYour roles: {', '.join([role.name for role in member.roles])}", 
                ephemeral=True
            )
            return

        # Check if the user already has a custom booster role
        custom_role_id, is_active = self._get_custom_role(member.id, guild.id)
        if custom_role_id:
            custom_role = nextcord.utils.get(guild.roles, id=custom_role_id)
            
            if custom_role:  # If the role still exists
                if is_active:
                    await interaction.response.send_message(f"You already have a custom role: **{custom_role.name}**. Use `/booster update` to modify it.", ephemeral=True)
                    return
                else:
                    # If the role exists but is inactive, simply reactivate it
                    await member.add_roles(custom_role)
                    self._update_role_status(member.id, guild.id, True)
                    await interaction.response.send_message(f"Reclaimed your custom role: **{custom_role.name}**!")
                    return

        # Check if the hex code is valid
        if not hex_code.startswith("#") or len(hex_code) != 7:
            await interaction.response.send_message("Invalid hex code! Please use a format like #ff5733.")
            return

        try:
            # Convert hex to Colour object
            color = Colour(int(hex_code[1:], 16))

            # Create a new custom role
            new_role = await guild.create_role(
                name=role_name,
                colour=color,
                reason=f"Custom role for booster {member.name}",
            )

            # Ensure the bot has permission to modify roles
            bot_role = guild.me.top_role
            booster_role = nextcord.utils.get(guild.roles, name=self.booster_role_name)
            
            if booster_role and bot_role.position <= booster_role.position:
                await interaction.response.send_message("The bot's role must be higher than the booster role to create this role!", ephemeral=True)
                await new_role.delete()  # Clean up the role we just created
                return

            # Find the position of the booster role and move the custom role above it
            if booster_role:
                booster_role_position = booster_role.position
                try:
                    await new_role.edit(position=booster_role_position + 1)
                except Exception as e:
                    # If we can't position it above the booster role, continue anyway
                    await interaction.followup.send(f"Note: Couldn't position the role above {self.booster_role_name}: {str(e)}", ephemeral=True)

            # Add the newly created role to the user
            await member.add_roles(new_role)
            
            # Store the role ID in our database
            self._save_custom_role(member.id, new_role.id, guild.id, True)

            await interaction.response.send_message(f"Created your custom role **{role_name}** with color **{hex_code}**!")

        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
            
    @booster.subcommand()
    async def update(
        self,
        interaction: nextcord.Interaction,
        new_name: str = SlashOption(description="New name for your custom role", required=False),
        new_color: str = SlashOption(description="New hex code for the role color (e.g., #ff5733)", required=False),
        bypass_check: bool = SlashOption(description="Admin-only: Bypass booster check", required=False, default=False)
    ):
        """Update your existing custom role."""
        member = interaction.user
        guild = interaction.guild
        
        # Check if the user is a server booster by role or is an admin bypassing
        is_booster = self._is_booster(member, guild)
        is_admin = member.guild_permissions.administrator
        if not is_booster and not (bypass_check and is_admin):
            await interaction.response.send_message("You must be a server booster to use this command!", ephemeral=True)
            return
        
        # Check if the user has a custom role
        custom_role_id, is_active = self._get_custom_role(member.id, guild.id)
        if not custom_role_id:
            await interaction.response.send_message("You don't have a custom role to update! Use `/booster claim` first.", ephemeral=True)
            return
        
        if not is_active:
            await interaction.response.send_message("Your custom role is currently removed. Use `/booster claim` to reclaim it first.", ephemeral=True)
            return
            
        custom_role = nextcord.utils.get(guild.roles, id=custom_role_id)
        
        if not custom_role:
            # Role no longer exists
            self._delete_custom_role(member.id, guild.id)
            await interaction.response.send_message("Your custom role was not found. You can create a new one with `/booster claim`.", ephemeral=True)
            return
            
        # Update the role
        try:
            update_kwargs = {}
            
            if new_name:
                update_kwargs["name"] = new_name
                
            if new_color:
                if not new_color.startswith("#") or len(new_color) != 7:
                    await interaction.response.send_message("Invalid hex code! Please use a format like #ff5733.")
                    return
                update_kwargs["colour"] = Colour(int(new_color[1:], 16))
                
            if not update_kwargs:
                await interaction.response.send_message("Please provide a new name or color to update your role.", ephemeral=True)
                return
                
            await custom_role.edit(**update_kwargs, reason=f"Custom role update for {member.name}")
            
            response_message = "Updated your custom role: "
            if new_name:
                response_message += f"name to **{new_name}** "
            if new_color:
                response_message += f"color to **{new_color}** "
                
            await interaction.response.send_message(response_message)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
            
    @booster.subcommand()
    async def remove(
        self, 
        interaction: nextcord.Interaction,
        bypass_check: bool = SlashOption(description="Admin-only: Bypass booster check", required=False, default=False)
    ):
        """Remove your custom role (without deleting it)."""
        member = interaction.user
        guild = interaction.guild
        
        # Check if the user is a server booster by role or is an admin bypassing
        is_booster = self._is_booster(member, guild)
        is_admin = member.guild_permissions.administrator
        if not is_booster and not (bypass_check and is_admin):
            await interaction.response.send_message("You must be a server booster to use this command!", ephemeral=True)
            return
        
        custom_role_id, is_active = self._get_custom_role(member.id, guild.id)
        if not custom_role_id:
            await interaction.response.send_message("You don't have a custom role to remove!", ephemeral=True)
            return
            
        if not is_active:
            await interaction.response.send_message("Your custom role is already removed!", ephemeral=True)
            return
            
        custom_role = nextcord.utils.get(guild.roles, id=custom_role_id)
        
        if custom_role:
            try:
                # Remove the role from the user instead of deleting it
                await member.remove_roles(custom_role)
                # Mark the role as inactive in the database
                self._update_role_status(member.id, guild.id, False)
                await interaction.response.send_message("Your custom role has been removed. You can reclaim it anytime with `/booster claim`.")
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
        else:
            # Role no longer exists
            self._delete_custom_role(member.id, guild.id)
            await interaction.response.send_message("Your custom role was already removed or deleted from the server.", ephemeral=True)
            
    @booster.subcommand()
    async def reclaim(
        self, 
        interaction: nextcord.Interaction,
        bypass_check: bool = SlashOption(description="Admin-only: Bypass booster check", required=False, default=False)
    ):
        """Reclaim your previously removed custom role."""
        member = interaction.user
        guild = interaction.guild
        
        # Check if the user is a server booster by role or is an admin bypassing
        is_booster = self._is_booster(member, guild)
        is_admin = member.guild_permissions.administrator
        if not is_booster and not (bypass_check and is_admin):
            await interaction.response.send_message("You must be a server booster to use this command!", ephemeral=True)
            return
        
        custom_role_id, is_active = self._get_custom_role(member.id, guild.id)
        if not custom_role_id:
            await interaction.response.send_message("You don't have a custom role to reclaim! Use `/booster claim` to create one.", ephemeral=True)
            return
            
        if is_active:
            await interaction.response.send_message("Your custom role is already active!", ephemeral=True)
            return
            
        custom_role = nextcord.utils.get(guild.roles, id=custom_role_id)
        
        if custom_role:
            try:
                await member.add_roles(custom_role)
                self._update_role_status(member.id, guild.id, True)
                await interaction.response.send_message(f"Reclaimed your custom role: **{custom_role.name}**!")
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
        else:
            # Role no longer exists
            self._delete_custom_role(member.id, guild.id)
            await interaction.response.send_message("Your custom role no longer exists. Please use `/booster claim` to create a new one.", ephemeral=True)
    
    @booster.subcommand()
    @commands.has_permissions(administrator=True)
    async def set_booster_role(
        self, 
        interaction: nextcord.Interaction, 
        role_name: str = SlashOption(description="Name of the server booster role")
    ):
        """[Admin only] Set the name of the server booster role."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
            return
            
        guild = interaction.guild
        
        # Check if the role exists
        role = nextcord.utils.get(guild.roles, name=role_name)
        if not role:
            await interaction.response.send_message(
                f"Warning: Role '{role_name}' was not found in this server. "
                f"Make sure the name matches exactly (case-sensitive).", 
                ephemeral=True
            )
            
        # Save the new booster role name
        self._save_config(guild.id, role_name)
        await interaction.response.send_message(f"Booster role has been set to: **{role_name}**")
    
    @booster.subcommand()
    @commands.has_permissions(administrator=True)
    async def admin_debug(self, interaction: nextcord.Interaction, user: nextcord.Member = SlashOption(description="User to check")):
        """[Admin only] Debug booster status and role information for a user."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("This command is for administrators only.", ephemeral=True)
            return
            
        guild = interaction.guild
        booster_role = nextcord.utils.get(guild.roles, name=self.booster_role_name)
        is_booster = booster_role in user.roles if booster_role else False
        
        custom_role_id, is_active = self._get_custom_role(user.id, guild.id)
        custom_role = nextcord.utils.get(guild.roles, id=custom_role_id) if custom_role_id else None
        
        debug_info = [
            f"**User**: {user.name} (ID: {user.id})",
            f"**Current Booster Role Name**: {self.booster_role_name}",
            f"**Booster Role Exists**: {'Yes' if booster_role else 'No'}",
            f"**Has Booster Role**: {'Yes' if is_booster else 'No'}",
            f"**User Roles**: {', '.join([role.name for role in user.roles])}",
            f"**Custom Role in DB**: {'Yes' if custom_role_id else 'No'}",
            f"**Custom Role ID**: {custom_role_id if custom_role_id else 'None'}",
            f"**Custom Role Active**: {'Yes' if is_active else 'No'}",
            f"**Custom Role Exists**: {'Yes' if custom_role else 'No'}",
            f"**Custom Role Name**: {custom_role.name if custom_role else 'N/A'}"
        ]
        
        await interaction.response.send_message("\n".join(debug_info), ephemeral=True)
    def cog_unload(self):
        self.check_empty_channels.cancel()  # Cancel task when cog is unloaded

    async def check_eligibility(self, interaction: nextcord.Interaction) -> bool:
        """
        Check if the user is eligible to use the command:
        - Has Manage Channels permission OR
        - Is a server booster
        """
        # Get member object
        member = interaction.guild.get_member(interaction.user.id)
        
        # Check for either condition (admin OR booster)
        is_admin = interaction.user.guild_permissions.manage_channels
        is_booster = member is not None and member.premium_since is not None
        
        # Return True if either condition is met
        return is_admin or is_booster

    @nextcord.slash_command(
        name="tempvoice",
        description="Create a temporary voice channel that deletes when empty after being used"
    )
    async def temp_voice(
        self, 
        interaction: nextcord.Interaction,
        channel_name: str = nextcord.SlashOption(
            name="name",
            description="Name for the temporary voice channel",
            required=True
        ),
        user_limit: int = nextcord.SlashOption(
            name="limit",
            description="Maximum number of users (0 for unlimited, or 1-50)",
            required=False,
            default=0,
            min_value=0,
            max_value=50
        )
    ):
        # Check if user is eligible to use this command
        is_eligible = await self.check_eligibility(interaction)
        if not is_eligible:
            await interaction.response.send_message(
                "⛔ Only server boosters or users with Manage Channels permission can create temporary voice channels.",
                ephemeral=True
            )
            return
        
        # Validate user limit
        if user_limit < 0:
            user_limit = 0
        elif user_limit > 50:
            user_limit = 50
            
        # Create the temporary voice channel in the same category as the interaction
        category = interaction.channel.category
        
        # Create the temporary voice channel
        temp_channel = await interaction.guild.create_voice_channel(
            name=channel_name,
            category=category,
            user_limit=user_limit
        )
        
        # Add the channel to our tracking dictionary with creation time and "has_been_used" flag
        self.temp_channels[temp_channel.id] = {
            "channel": temp_channel,
            "created_at": time.time(),
            "has_been_used": False,
            "last_empty": None
        }
        
        # Create response message based on user limit
        if user_limit == 0:
            limit_msg = "with no user limit"
        else:
            limit_msg = f"with a limit of {user_limit} users"
            
        # Respond to the user
        await interaction.response.send_message(
            f"Temporary voice channel **{channel_name}** created {limit_msg}! It will be deleted when it's empty after being used, or after 1 hour if unused.",
            ephemeral=True
        )
        
        # If the user is in a voice channel, move them to the new one
        if interaction.user.voice:
            await interaction.user.move_to(temp_channel)
            
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Check if user joined one of our temp channels
        if after and after.channel and after.channel.id in self.temp_channels:
            # Mark channel as used once someone joins
            self.temp_channels[after.channel.id]["has_been_used"] = True
            self.temp_channels[after.channel.id]["last_empty"] = None
            
        # Check if user left one of our temp channels
        if before and before.channel and before.channel.id in self.temp_channels:
            # Wait a moment to allow for reconnections
            await asyncio.sleep(1)
            
            # If the channel is now empty and has been used
            if len(before.channel.members) == 0:
                channel_data = self.temp_channels[before.channel.id]
                
                # If it has been used before, mark when it became empty
                if channel_data["has_been_used"]:
                    channel_data["last_empty"] = time.time()
    
    @tasks.loop(seconds=30)
    async def check_empty_channels(self):
        """Background task to check and remove empty channels"""
        current_time = time.time()
        channels_to_remove = []
        
        for channel_id, data in list(self.temp_channels.items()):
            channel = data["channel"]
            
            # Case 1: Channel created but unused for over 1 hour - delete it
            if not data["has_been_used"] and (current_time - data["created_at"]) > 3600:  # 1 hour
                try:
                    await channel.delete(reason="Temporary voice channel unused for 1 hour")
                    channels_to_remove.append(channel_id)
                except (nextcord.NotFound, nextcord.HTTPException):
                    channels_to_remove.append(channel_id)
                    
            # Case 2: Channel was used but is now empty for over 30 seconds - delete it
            elif data["has_been_used"] and data["last_empty"] is not None:
                if (current_time - data["last_empty"]) > 30:  # 30 seconds of being empty
                    try:
                        await channel.delete(reason="Temporary voice channel is now empty after being used")
                        channels_to_remove.append(channel_id)
                    except (nextcord.NotFound, nextcord.HTTPException):
                        channels_to_remove.append(channel_id)
        
        # Remove deleted channels from our tracking dictionary
        for channel_id in channels_to_remove:
            self.temp_channels.pop(channel_id, None)
            
    @check_empty_channels.before_loop
    async def before_check_empty(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(BoosterPerks(bot))
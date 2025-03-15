import nextcord
from nextcord.ext import commands
from nextcord import slash_command, Interaction, SlashOption, Embed
import asyncio
import re
import json
import os
from datetime import datetime, timedelta

"""
    List of moderation commands: Kick, Ban, Mute, etc...
"""

class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.locked_channels = {}  # To keep track of locked channels and their timers
        self.data_file = "locked_channels.json"
        self.load_locked_channels()
        # Start recovery for channels that were locked before restart
        bot.loop.create_task(self.recover_locked_channels())
    
    @slash_command(name="kick", description="Kick a member from the server")
    async def kick(
           self,
            ctx: Interaction,
            member: nextcord.Member = nextcord.SlashOption(
                name="member",
                description="Member to kick",
                required=True,
            ),
            reason: str = nextcord.SlashOption(
                name="reason",
                description="Reason",
                required=False,
            )
    ): 
        if not ctx.user.guild_permissions.kick_members:
            await ctx.response.send_message(
                "❌ You do not have permission to use this command.", ephemeral=True #Only the user can see this message
            )
            return
           
        if not reason: 
            reason ="No reason provided"
        await member.kick(reason=reason)
        await ctx.response.send_message(f"{member.mention} has been **kicked** by {ctx.user.mention} for **{reason}**.")

    @slash_command(name="ban", description="Ban a member from the server")
    async def ban(
           self,
            ctx: Interaction,
            member: nextcord.Member = nextcord.SlashOption(
                name="member",
                description="Member to ban",
                required=True,
            ),
            reason: str = nextcord.SlashOption(
                name="reason",
                description="Reason",
                required=False,
            )
    ): 
        if not ctx.user.guild_permissions.ban_members:
            await ctx.response.send_message(
                "❌ You do not have permission to use this command.", ephemeral=True #Only the user can see this message
            )
            return
           
        if not reason: 
            reason ="No reason provided"
        await member.ban(reason=reason)
        await ctx.response.send_message(f"{member.mention} has been **banned** by {ctx.user.mention} for **{reason}**.")
           

    @nextcord.slash_command(name="mute", description="Mutes a member")
    async def mute(
        self,
        ctx: Interaction,
        member: nextcord.Member = SlashOption(
            name="member",
            description="Member to mute",
            required=True,
        ),
    ):
        # Check if user has permission
        if not ctx.user.guild_permissions.manage_roles:
            await ctx.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return

        # Find the Muted role, or create one if it doesn't exist
        muted_role = nextcord.utils.get(ctx.guild.roles, name="Muted")

        if not muted_role:
            try:
                muted_role = await ctx.guild.create_role(name="Muted", reason="Mute command used")
                
                # Deny send message permissions in all text channels
                for channel in ctx.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
            except nextcord.Forbidden:
                await ctx.response.send_message("I don't have permission to create roles.", ephemeral=True)
                return

        # Add the Muted role to the user
        if muted_role in member.roles:
            await ctx.response.send_message(f"{member.mention} is already muted.", ephemeral=True)
        else:
            await member.add_roles(muted_role)
            await ctx.response.send_message(f"{member.mention} has been muted.")     
          
    @nextcord.slash_command(name="purge", description="Deletes a specified number of messages from the channel.")
    async def purge(self, interaction: nextcord.Interaction, num: int):
        # Check if the user has the Manage Messages permission
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return

        # Purge the messages
        deleted = await interaction.channel.purge(limit=num)
        
        # Send a confirmation message
        await interaction.response.send_message(
            f"Deleted {len(deleted)} messages.", ephemeral=True
        )

    @nextcord.slash_command(
        name="sendmsg",
        description="Send a message to another channel via the bot."
    )
    async def sendmsg(
        self, 
        interaction: nextcord.Interaction, 
        channel: nextcord.TextChannel, 
        message: str,
        title: str = None  # Optional title/header
    ):
        # Check if the user has Manage Messages permission
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return
        
        # Check if the user has permission to send messages in the target channel
        if not channel.permissions_for(interaction.user).send_messages:
            await interaction.response.send_message(
                "You do not have permission to send messages in that channel.", ephemeral=True
            )
            return
        
        # Create an embed for the message
        embed = Embed(
            title=title if title else None,  # Set title if provided
            description=message,
            color=nextcord.Color.blue()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
 
        
        # Send the embed to the specified channel
        await channel.send(embed=embed)
        
        # Confirm action to the user
        await interaction.response.send_message(
            f"Message sent to {channel.mention}."
        )


    @nextcord.slash_command(name="setnick", description="Change your or someone else's nickname.")
    async def setnick(self, ctx: nextcord.Interaction, member: nextcord.Member, nickname: str):
        # Check if the user has Manage Nicknames permission
        if not ctx.user.guild_permissions.manage_nicknames:
            await ctx.send("You do not have permission to manage nicknames.")
            return

        try:
            # Change the nickname
            await member.edit(nick=nickname)
            await ctx.send(f"Successfully changed {member.mention}'s nickname to {nickname}.")
        except nextcord.errors.Forbidden:
            await ctx.send("I do not have permission to change that user's nickname.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    def load_locked_channels(self):
        """Load locked channels from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # Convert stored timestamps back to datetime objects
                    self.locked_channels = {
                        int(channel_id): datetime.fromtimestamp(timestamp) 
                        for channel_id, timestamp in data.items()
                    }
                print(f"Loaded {len(self.locked_channels)} locked channels from storage")
            except Exception as e:
                print(f"Error loading locked channels: {e}")
                self.locked_channels = {}
    
    def save_locked_channels(self):
        """Save locked channels to JSON file"""
        try:
            # Convert datetime objects to timestamps for JSON serialization
            data = {
                channel_id: unlock_time.timestamp() 
                for channel_id, unlock_time in self.locked_channels.items()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving locked channels: {e}")
    
    async def recover_locked_channels(self):
        """Recover locked channels after bot restart"""
        # Wait for bot to be fully ready
        await self.bot.wait_until_ready()
        
        current_time = datetime.now()
        channels_to_unlock = []
        
        # Process each locked channel
        for channel_id, unlock_time in list(self.locked_channels.items()):
            try:
                channel = self.bot.get_channel(int(channel_id))
                
                # If channel no longer exists or can't be accessed
                if not channel:
                    channels_to_unlock.append(channel_id)
                    continue
                
                # Calculate remaining time
                time_remaining = (unlock_time - current_time).total_seconds()
                
                # If unlock time has already passed
                if time_remaining <= 0:
                    await self.unlock_channel(channel, send_message=True, reason="bot_restart")
                    channels_to_unlock.append(channel_id)
                else:
                    # Reschedule unlock task
                    self.bot.loop.create_task(self.schedule_unlock(channel, time_remaining))
                    unlock_timestamp = int(unlock_time.timestamp())
                    await channel.send(
                        f"🔒 **Channel lock restored**\n"
                        f"This channel was locked before the bot restarted.\n"
                        f"It will be unlocked <t:{unlock_timestamp}:F>."
                    )
            except Exception as e:
                print(f"Error recovering channel {channel_id}: {e}")
                channels_to_unlock.append(channel_id)
        
        # Remove channels that no longer exist or had errors
        for channel_id in channels_to_unlock:
            if channel_id in self.locked_channels:
                del self.locked_channels[channel_id]
        
        self.save_locked_channels()
    
    @slash_command(
        name="shutdown",
        description="Lock a channel for a specified duration. No one will be able to send messages."
    )
    async def shutdown(
        self, 
        interaction: nextcord.Interaction,
        duration: str = SlashOption(
            name="duration",
            description="Duration format: number + s/m/h/d/w (e.g., 30s, 5m, 2h, 1d, 1w)",
            required=True
        )
    ):
        # Check if user has permission to manage channels
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to lock channels.", ephemeral=True)
            return
        
        # Parse duration
        duration_seconds = self.parse_duration(duration)
        if duration_seconds is None:
            await interaction.response.send_message(
                "Invalid duration format. Please use a number followed by s/m/h/d/w (e.g., 30s, 5m, 2h, 1d, 1w).",
                ephemeral=True
            )
            return
        
        channel = interaction.channel
        
        # Check if the channel is already locked
        if channel.id in self.locked_channels:
            await interaction.response.send_message(
                f"This channel is already locked. It will be unlocked at <t:{int(self.locked_channels[channel.id].timestamp())}:F>.",
                ephemeral=True
            )
            return
        
        # Calculate unlock time
        unlock_time = datetime.now() + timedelta(seconds=duration_seconds)
        self.locked_channels[channel.id] = unlock_time
        # Save to persistent storage
        self.save_locked_channels()
        
        # Save current permissions for everyone role
        everyone_role = interaction.guild.default_role
        current_permissions = channel.overwrites_for(everyone_role)
        
        # Create new permissions overwrite with send_messages set to False
        new_permissions = nextcord.PermissionOverwrite(**dict(current_permissions))
        new_permissions.send_messages = False
        
        # Apply the permission change
        await channel.set_permissions(everyone_role, overwrite=new_permissions)
        
        # Format the duration for the message
        formatted_duration = self.format_duration_message(duration_seconds)
        unlock_timestamp = int(unlock_time.timestamp())
        
        # Respond to the interaction
        await interaction.response.send_message(
            f"🔒 **Channel locked** by {interaction.user.mention}\n"
            f"This channel has been locked for {formatted_duration}.\n"
            f"It will be unlocked at <t:{unlock_timestamp}:F>."
        )
        
        # Schedule the unlock
        self.bot.loop.create_task(self.schedule_unlock(channel, duration_seconds))
    
    async def schedule_unlock(self, channel, duration_seconds):
        try:
            await asyncio.sleep(duration_seconds)
            # Only proceed if the channel is still locked
            if channel.id in self.locked_channels:
                await self.unlock_channel(channel, send_message=True, reason="timer_expired")
            
        except Exception as e:
            print(f"Error in unlock schedule: {e}")
    
    async def unlock_channel(self, channel, send_message=True, reason="manual"):
        """Unlock a channel"""
        if channel.id in self.locked_channels:
            try:
                # Restore original permissions
                everyone_role = channel.guild.default_role
                current_permissions = channel.overwrites_for(everyone_role)
                new_permissions = nextcord.PermissionOverwrite(**dict(current_permissions))
                new_permissions.send_messages = None  # Reset to default
                
                await channel.set_permissions(everyone_role, overwrite=new_permissions)
                del self.locked_channels[channel.id]
                self.save_locked_channels()
                
                # Send unlock notification based on reason
                if send_message:
                    if reason == "timer_expired":
                        await channel.send("🔓 **Channel unlocked**\nThe lockdown period has ended. Members can now send messages in this channel again.")
                    elif reason == "bot_restart":
                        await channel.send("🔓 **Channel unlocked**\nThis channel was previously locked, but the lockdown period expired while the bot was offline.")
                    elif reason == "manual":
                        await channel.send("🔓 **Channel unlocked manually**\nAn administrator has ended the lockdown. Members can now send messages in this channel again.")
                    else:
                        await channel.send("🔓 **Channel unlocked**\nMembers can now send messages in this channel again.")
                return True
            except Exception as e:
                print(f"Error unlocking channel {channel.id}: {e}")
        return False
    
    @slash_command(
        name="unlock",
        description="Manually unlock a locked channel."
    )
    async def unlock(self, interaction: nextcord.Interaction):
        # Check if user has permission to manage channels
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to unlock channels.", ephemeral=True)
            return
            
        channel = interaction.channel
        
        # Check if the channel is locked
        if channel.id not in self.locked_channels:
            await interaction.response.send_message("This channel is not locked.", ephemeral=True)
            return
            
        success = await self.unlock_channel(channel, send_message=False, reason="manual")
        
        if success:
            await interaction.response.send_message("🔓 **Channel unlocked manually**\nMembers can now send messages in this channel again.")
        else:
            await interaction.response.send_message("There was an error unlocking the channel. Please try again.", ephemeral=True)
    
    def parse_duration(self, duration_str):
        """Parse a duration string into seconds."""
        # Regular expression to match the format
        pattern = re.compile(r'^(\d+)([smhdw])$')
        match = pattern.match(duration_str)
        
        if not match:
            return None
            
        value, unit = match.groups()
        value = int(value)
        
        # Convert to seconds based on unit
        if unit == 's':
            return value
        elif unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 3600
        elif unit == 'd':
            return value * 86400
        elif unit == 'w':
            return value * 604800
        else:
            return None
    
    def format_duration_message(self, seconds):
        """Format seconds into a human-readable duration message."""
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        
        days = hours // 24
        if days < 7:
            return f"{days} day{'s' if days != 1 else ''}"
        
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''}"

def setup(bot):  
    bot.add_cog(Mod(bot))
import asyncio
import datetime
import re
import typing

import nextcord
from nextcord.ext import commands
import wavelink


class MusicCog(commands.Cog):
    """Music commands using Wavelink (Lavalink wrapper)"""

    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.connect_nodes())

    async def connect_nodes(self):
        """Connect to Lavalink nodes when the bot is ready."""
        await self.bot.wait_until_ready()
        
        # Configure this with your Lavalink server details
        await wavelink.NodePool.create_node(
            bot=self.bot,
            host='127.0.0.1',  # Your Lavalink server address
            port=2333,         # Your Lavalink server port
            password='youshallnotpass',  # Your Lavalink password
            https=False
        )
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a wavelink node is ready."""
        print(f'Node {node.identifier} is ready!')
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason):
        """Event fired when a track ends."""
        if not player.queue.is_empty and not reason == "REPLACED":
            next_track = player.queue.get()
            await player.play(next_track)
            
            # Send now playing message
            if hasattr(player, 'text_channel'):
                await player.text_channel.send(f"Now playing: **{next_track.title}**")
    
    async def get_player(self, ctx):
        """Get or create a wavelink player for a guild."""
        if not ctx.voice_client:
            # Create a player if one doesn't exist
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            # Store the text channel for later use
            setattr(vc, 'text_channel', ctx.channel)
            return vc
        return ctx.voice_client
    
    @commands.command(name="connect", aliases=["join"])
    async def connect_command(self, ctx):
        """Connect to the voice channel."""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel to use this command.")
        
        if ctx.voice_client:
            return await ctx.send("I'm already connected to a voice channel.")
        
        await self.get_player(ctx)
        await ctx.send(f"Connected to {ctx.author.voice.channel.mention}!")
    
    @commands.command(name="disconnect", aliases=["leave", "dc"])
    async def disconnect_command(self, ctx):
        """Disconnect from the voice channel."""
        if not ctx.voice_client:
            return await ctx.send("I'm not connected to any voice channel.")
        
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from voice channel.")
    
    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx, *, query: str):
        """Play a song or add it to the queue."""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel to use this command.")
        
        player = await self.get_player(ctx)
        
        # Check if the query is a URL or a search term
        if not re.match(r"http[s]?://", query):
            query = f"ytsearch:{query}"
        
        # Search for the track
        tracks = await wavelink.NodePool.get_node().get_tracks(query=query)
        
        if not tracks:
            return await ctx.send("No songs found with that query.")
        
        # Handle playlist or single track
        if isinstance(tracks, wavelink.TrackPlaylist):
            for track in tracks.tracks:
                player.queue.put(track)
            await ctx.send(f"Added playlist **{tracks.data['playlistInfo']['name']}** with {len(tracks.tracks)} tracks to the queue.")
        else:
            track = tracks[0]
            
            # If nothing is playing, play the track, else add to queue
            if not player.is_playing():
                await player.play(track)
                await ctx.send(f"Now playing: **{track.title}**")
            else:
                player.queue.put(track)
                await ctx.send(f"Added **{track.title}** to the queue.")
    
    @commands.command(name="pause")
    async def pause_command(self, ctx):
        """Pause the currently playing track."""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now.")
        
        player = ctx.voice_client
        
        if player.is_paused():
            return await ctx.send("The player is already paused.")
        
        await player.pause()
        await ctx.send("Paused the player.")
    
    @commands.command(name="resume")
    async def resume_command(self, ctx):
        """Resume the currently paused track."""
        if not ctx.voice_client:
            return await ctx.send("I'm not connected to any voice channel.")
        
        player = ctx.voice_client
        
        if not player.is_paused():
            return await ctx.send("The player is not paused.")
        
        await player.resume()
        await ctx.send("Resumed the player.")
    
    @commands.command(name="skip", aliases=["next"])
    async def skip_command(self, ctx):
        """Skip the currently playing track."""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now.")
        
        player = ctx.voice_client
        
        if player.queue.is_empty:
            await player.stop()
            return await ctx.send("Skipped the current track. No more tracks in the queue.")
        
        await player.stop()
        await ctx.send("Skipped the current track.")
    
    @commands.command(name="queue", aliases=["q"])
    async def queue_command(self, ctx):
        """Display the current queue."""
        if not ctx.voice_client:
            return await ctx.send("I'm not connected to any voice channel.")
        
        player = ctx.voice_client
        
        if player.queue.is_empty:
            return await ctx.send("The queue is empty.")
        
        queue_list = []
        for i, track in enumerate(player.queue._queue, start=1):
            queue_list.append(f"{i}. **{track.title}** ({self.format_duration(track.duration)})")
        
        # Create an embed for the queue
        embed = nextcord.Embed(
            title="Queue",
            description="\n".join(queue_list[:10]),
            color=nextcord.Color.blurple()
        )
        
        if player.is_playing():
            current = player.track
            embed.add_field(
                name="Currently Playing",
                value=f"**{current.title}** ({self.format_duration(current.duration)})",
                inline=False
            )
        
        # Add a note if there are more tracks than shown
        if len(player.queue._queue) > 10:
            embed.set_footer(text=f"And {len(player.queue._queue) - 10} more tracks...")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_command(self, ctx):
        """Display information about the currently playing track."""
        if not ctx.voice_client or not hasattr(ctx.voice_client, 'track') or not ctx.voice_client.track:
            return await ctx.send("Nothing is playing right now.")
        
        player = ctx.voice_client
        current = player.track
        
        embed = nextcord.Embed(
            title="Now Playing",
            description=f"**{current.title}**",
            color=nextcord.Color.green()
        )
        
        embed.add_field(name="Duration", value=self.format_duration(current.duration), inline=True)
        embed.add_field(name="Requested By", value=ctx.author.mention, inline=True)
        
        # Add a progress bar
        position = player.position
        duration = current.duration
        percentage = position / duration if duration > 0 else 0
        
        progress_bar = "▬" * 20
        position_marker = round(percentage * 20)
        progress_bar = progress_bar[:position_marker] + "🔘" + progress_bar[position_marker + 1:]
        
        embed.add_field(
            name="Progress",
            value=f"{self.format_duration(position)} {progress_bar} {self.format_duration(duration)}",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="volume", aliases=["vol"])
    async def volume_command(self, ctx, volume: int = None):
        """Change or display the player volume."""
        if not ctx.voice_client:
            return await ctx.send("I'm not connected to any voice channel.")
        
        player = ctx.voice_client
        
        if volume is None:
            return await ctx.send(f"Current volume: **{player.volume}%**")
        
        if not 0 <= volume <= 100:
            return await ctx.send("Volume must be between 0 and 100.")
        
        await player.set_volume(volume)
        await ctx.send(f"Volume set to **{volume}%**")
    
    @commands.command(name="loop")
    async def loop_command(self, ctx):
        """Toggle loop for the current track."""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now.")
        
        player = ctx.voice_client
        
        # We'll implement loop by storing a flag on the player
        player.loop = not getattr(player, 'loop', False)
        
        await ctx.send(f"Track loop: **{'Enabled' if player.loop else 'Disabled'}**")
    
    @commands.command(name="clear")
    async def clear_command(self, ctx):
        """Clear the queue."""
        if not ctx.voice_client:
            return await ctx.send("I'm not connected to any voice channel.")
        
        player = ctx.voice_client
        
        if player.queue.is_empty:
            return await ctx.send("The queue is already empty.")
        
        player.queue.clear()
        await ctx.send("Cleared the queue.")
    
    @staticmethod
    def format_duration(duration: int):
        """Format milliseconds to a readable time format."""
        minutes, seconds = divmod(duration // 1000, 60)
        hours, minutes = divmod(minutes, 60)
        
        time_format = ""
        if hours > 0:
            time_format += f"{hours:02d}:"
        
        return f"{time_format}{minutes:02d}:{seconds:02d}"


def setup(bot):
    bot.add_cog(MusicCog(bot))
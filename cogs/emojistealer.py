import nextcord
from nextcord.ext import commands
import re
import aiohttp
import io

class EmojiStealer(commands.Cog):
    

    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="steal")
    @commands.has_permissions(manage_emojis=True)
    async def steal(self, ctx, emoji: str = None):
       
        
        if emoji is None:
            await ctx.send("Please provide an emoji to steal! Usage: `$steal [emoji]`")
            return
            
        #Match custom emoji pattern
        emoji_pattern = r'<a?:([a-zA-Z0-9_]+):([0-9]+)>'
        match = re.match(emoji_pattern, emoji)
        
        if not match:
            await ctx.send("That doesn't seem to be a custom emoji. Please try again with a valid custom emoji.")
            return
            
        #Extract emoji name and ID
        emoji_name = match.group(1)
        emoji_id = match.group(2)
        is_animated = emoji.startswith("<a:")
        
        #Construct emoji URL
        emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if is_animated else 'png'}"
        
        #Download the emoji
        async with aiohttp.ClientSession() as session:
            async with session.get(emoji_url) as response:
                if response.status != 200:
                    await ctx.send(f"Failed to download the emoji. Status code: {response.status}")
                    return
                
                emoji_bytes = await response.read()
                
        #Create a file-like object from the emoji bytes
        emoji_file = io.BytesIO(emoji_bytes)
        
        try:
            #Create the emoji in the server
            new_emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=emoji_file.read())
            await ctx.send(f"Successfully added {new_emoji} to the server!")
        except nextcord.Forbidden:
            await ctx.send("I don't have the required permissions to add emojis to this server.")
        except nextcord.HTTPException as e:
            if e.status == 400:
                await ctx.send("Failed to add emoji. The file may be too large or the server may have reached its emoji limit.")
            else:
                await ctx.send(f"An error occurred while adding the emoji: {e}")

    @steal.error
    async def steal_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the 'Manage Emojis' permission to use this command.")
        else:
            await ctx.send(f"An error occurred: {str(error)}")

def setup(bot):
    bot.add_cog(EmojiStealer(bot))
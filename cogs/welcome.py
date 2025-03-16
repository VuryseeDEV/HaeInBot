import nextcord
from nextcord.ext import commands
from nextcord import File, Embed, SlashOption
from io import BytesIO
import aiohttp
from PIL import Image

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channels = {}  # Dictionary to store welcome channels for each guild
        # Create an aiohttp session for async requests
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        # Clean up the aiohttp session when the cog is unloaded
        if self.session and not self.session.closed:
            self.bot.loop.create_task(self.session.close())

    @nextcord.slash_command(name="welcome", description="Set the welcome channel for new members")
    async def welcome(self, interaction: nextcord.Interaction):
        # This is just a base command that won't be called directly
        pass

    @welcome.subcommand(name="setchannel", description="Set the welcome channel for new members")
    async def set_welcome_channel(
        self, 
        interaction: nextcord.Interaction, 
        channel: nextcord.abc.GuildChannel = SlashOption(
            name="channel",
            description="The channel to send welcome messages to",
            required=True
        )
    ):
        guild_id = interaction.guild.id
        if isinstance(channel, nextcord.TextChannel):
            self.welcome_channels[guild_id] = channel.id
            await interaction.response.send_message(f"Welcome channel set to {channel.mention}!", ephemeral=True)
        else:
            await interaction.response.send_message("Please select a text channel!", ephemeral=True)

    @welcome.subcommand(name="test", description="Test the welcome message with your profile")
    async def test_welcome(self, interaction: nextcord.Interaction):
        """Test the welcome message using your own profile"""
        guild_id = interaction.guild.id
        
        # Check if a welcome channel has been set for this guild
        if guild_id not in self.welcome_channels:
            await interaction.response.send_message("Please set a welcome channel first using `/welcome setchannel`!", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        member = interaction.user
        welcome_image = await self.create_welcome_image(member)

        # Create the embed with the welcome message
        embed = Embed(
            title="Welcome to the server!",
            description=f"Welcome {member.mention} to {interaction.guild.name}! We're happy to have you here.",
            color=nextcord.Color.red()
        )

        # Attach the welcome image to the embed
        embed.set_image(url="attachment://welcome_banner.png")

        # Send the embed with the image
        await interaction.followup.send(
            content=f"Here's a test of the welcome message:",
            embed=embed, 
            file=File(welcome_image, filename="welcome_banner.png")
        )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        guild_id = guild.id
        
        # Check if a welcome channel has been set for this guild
        if guild_id in self.welcome_channels:
            welcome_channel_id = self.welcome_channels[guild_id]
            welcome_channel = guild.get_channel(welcome_channel_id)
            
            if welcome_channel is not None:
                try:
                    welcome_image = await self.create_welcome_image(member)

                    # Create the embed with the welcome message
                    embed = Embed(
                        title="Welcome to the server!",
                        description=f"Welcome {member.mention} to {guild.name}! We're happy to have you here.",
                        color=nextcord.Color.red()
                    )

                    # Attach the welcome image to the embed
                    embed.set_image(url="attachment://welcome_banner.png")

                    # Send the embed with the image
                    await welcome_channel.send(
                        content=f"Welcome {member.mention}!", 
                        embed=embed, 
                        file=File(welcome_image, filename="welcome_banner.png")
                    )
                except Exception as e:
                    print(f"Error in welcome message: {e}")
                    # Send a simpler welcome message if image creation fails
                    await welcome_channel.send(f"Welcome to {guild.name}, {member.mention}!")

    async def create_welcome_image(self, member):
        try:
            background_image_path = "assets/botwelcombanner.jpg"
            img = Image.open(background_image_path)
        
            img = img.resize((600, 200))  # Modify this as needed

            # Get avatar url, handle the case where member has no avatar
            if member.avatar:
                avatar_url = member.avatar.url
            else:
                avatar_url = member.default_avatar.url
                
            avatar = await self.get_avatar_image(avatar_url)

            # Create a circular mask for the avatar
            mask = Image.new("L", avatar.size, 0)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
            
            # Apply the mask to create a circular avatar
            avatar.putalpha(mask)

            bg_width, bg_height = img.size
            avatar_width, avatar_height = avatar.size

            avatar_position = ((bg_width - avatar_width) // 2, (bg_height - avatar_height) // 2)

            # Create a transparent overlay to paste the avatar
            transparent = Image.new("RGBA", img.size, (0, 0, 0, 0))
            transparent.paste(avatar, avatar_position, avatar)
            
            # Convert background to RGBA if it's not already
            if img.mode != "RGBA":
                img = img.convert("RGBA")
                
            # Composite the images
            final_img = Image.alpha_composite(img, transparent)

            byte_io = BytesIO()
            final_img.save(byte_io, "PNG")
            byte_io.seek(0)
            
            return byte_io
        except Exception as e:
            print(f"Error creating welcome image: {e}")
            # Create a simple fallback image
            fallback = Image.new("RGB", (600, 200), (47, 49, 54))  # Discord dark theme color
            byte_io = BytesIO()
            fallback.save(byte_io, "PNG")
            byte_io.seek(0)
            return byte_io

    async def get_avatar_image(self, url):
        # Fetch and open the avatar image asynchronously
        async with self.session.get(url) as response:
            if response.status == 200:
                avatar_data = await response.read()
                avatar_img = Image.open(BytesIO(avatar_data))
                
                # Make the avatar larger for a better welcome image
                avatar_size = 100
                avatar_img = avatar_img.resize((avatar_size, avatar_size))
                
                # Convert to RGBA to support transparency
                if avatar_img.mode != "RGBA":
                    avatar_img = avatar_img.convert("RGBA")
                    
                return avatar_img
            else:
                # Create a default avatar if we can't get the user's
                default = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
                return default

def setup(bot):
    bot.add_cog(Welcome(bot))
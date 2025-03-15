import nextcord
from nextcord.ext import commands
from nextcord.ui import Button, View
import os

class RulesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="rules")
    async def rules(self, ctx):
        # Create a button that sends the server rules when clicked
        button = Button(label="View Rules", style=nextcord.ButtonStyle.primary)
        
        # Define what happens when the button is clicked
        async def button_callback(interaction: nextcord.Interaction):
            # Create an embed for the rules
            embed = nextcord.Embed(
                title="Server Rules",
                description="Please read and follow these rules to maintain a friendly community.",
                color=nextcord.Color.blue()
            )
            
            # Add each rule in a separate line (rows)
            rules_text = (
                "1. **Respect Everyone**\nTreat all members with respect.\n\n"
                "2. **No Spamming**\nAvoid spamming messages, images, or emojis.\n\n"
                "3. **Follow Moderator Instructions**\nListen to the moderators and admins.\n\n"
                "4. **No NSFW**\nKeep the content safe for all audiences.\n\n"
                "Feel free to reach out to the moderators if you have any questions."
            )
            embed.add_field(name="Rules:", value=rules_text, inline=False)
            
            # Add footer text
            embed.set_footer(text="Thank you for being part of our community!")

            # Get the path to your banner image
            banner_path = "assets/banner.png"  # Replace with your actual file path

            # Check if the file exists in the assets folder
            if os.path.exists(banner_path):
                # Send the banner image as an attachment
                with open(banner_path, 'rb') as file:
                    picture = nextcord.File(file, filename="banner.png")
                    embed.set_image(url="attachment://banner.png")
                    await interaction.response.send_message(embed=embed, file=picture, ephemeral=True)
            else:
                # If the file doesn't exist, send a message without the image
                await interaction.response.send_message(embed=embed, ephemeral=True)

        # Attach the callback function to the button
        button.callback = button_callback
        
        # Create a view to hold the button
        view = View()
        view.add_item(button)

        # Send the banner with the button in the channel
        await ctx.send("Welcome to the server! Click the button below to view the server rules.", view=view)

# Add the cog to the bot
def setup(bot):
    bot.add_cog(RulesCog(bot))

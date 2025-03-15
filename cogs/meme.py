import nextcord
from nextcord.ext import commands
import aiohttp
import random
import io

class MemeGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Popular meme templates from memegen.link
        self.templates = [
            "drake", "distracted", "fry", "doge", "changemymind", 
            "twobuttons", "spongebob", "patrick", "brain", "rollsafe",
            "pikachu", "stonks", "kermit", "thisisfine", "gru-plan",
            "batman", "buzz", "sanders", "car-drift", "hotline-bling"
        ]
        # Dict of popular phrases for different meme templates
        self.template_texts = {
            "drake": [
                ["Using paid meme APIs", "Using free meme APIs"],
                ["Making memes manually", "Using a Discord bot to make memes"],
                ["Studying", "Making Discord bots"]
            ],
            "distracted": [
                ["Me", "New Discord features", "My current bot project"],
                ["Developers", "New programming language", "Existing project"]
            ],
            "fry": [
                ["Not sure if bug", "Or just a feature"],
                ["Not sure if Discord is slow", "Or my internet is bad"],
                ["Not sure if my code is good", "Or I just got lucky"]
            ],
            "changemymind": [
                ["Discord bots", "Are the best bots"],
                ["Nextcord", "Is awesome"],
                ["Memes", "Make discord servers better"]
            ],
            # Default texts for other templates
            "default": [
                ["Top text", "Bottom text"],
                ["When the code works", "But you don't know why"],
                ["Discord bots", "Making servers fun since forever"]
            ]
        }
        
    @nextcord.slash_command(name="meme", description="Generate a random meme")
    async def meme(self, interaction: nextcord.Interaction):
        await interaction.response.defer()
        
        try:
            # Pick a random template
            template = random.choice(self.templates)
            
            # Get appropriate text for this template
            if template in self.template_texts:
                texts = random.choice(self.template_texts[template])
            else:
                texts = random.choice(self.template_texts["default"])
            
            # URL encode the texts
            encoded_texts = [nextcord.utils.escape_mentions(text) for text in texts]
            
            # Build the URL for memegen.link
            if len(texts) == 2:
                url = f"https://api.memegen.link/images/{template}/{encoded_texts[0]}/{encoded_texts[1]}.png"
            elif len(texts) > 2:  # Some memes might have more text fields
                url = f"https://api.memegen.link/images/{template}/{'/'.join(encoded_texts)}.png"
            else:
                url = f"https://api.memegen.link/images/{template}/{encoded_texts[0]}.png"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        file = nextcord.File(io.BytesIO(data), filename="meme.png")
                        await interaction.followup.send(file=file)
                    else:
                        await interaction.followup.send(f"Failed to generate meme: {response.status}")
        except Exception as e:
            await interaction.followup.send(f"Error generating meme: {str(e)}")
    
    @nextcord.slash_command(name="custommeme", description="Create a custom meme with your own text")
    async def custom_meme(self, interaction: nextcord.Interaction,
                         template: str = nextcord.SlashOption(
                             name="template",
                             description="Meme template to use",
                             required=True,
                             choices={"Drake": "drake", "Distracted Boyfriend": "distracted", "Not Sure If": "fry", 
                                     "Change My Mind": "changemymind", "Two Buttons": "twobuttons"}
                         ),
                         top_text: str = nextcord.SlashOption(
                             name="top_text",
                             description="Text for the top of the meme",
                             required=True
                         ),
                         bottom_text: str = nextcord.SlashOption(
                             name="bottom_text",
                             description="Text for the bottom of the meme",
                             required=True
                         )):
        await interaction.response.defer()
        
        try:
            # URL encode the texts
            encoded_top = nextcord.utils.escape_mentions(top_text)
            encoded_bottom = nextcord.utils.escape_mentions(bottom_text)
            
            # Build the URL
            url = f"https://api.memegen.link/images/{template}/{encoded_top}/{encoded_bottom}.png"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        file = nextcord.File(io.BytesIO(data), filename="custom_meme.png")
                        await interaction.followup.send(file=file)
                    else:
                        await interaction.followup.send(f"Failed to generate meme: {response.status}")
        except Exception as e:
            await interaction.followup.send(f"Error generating meme: {str(e)}")
    
    @nextcord.slash_command(name="memetemplates", description="List available meme templates")
    async def list_templates(self, interaction: nextcord.Interaction):
        templates_list = "\n".join([f"• {template}" for template in self.templates])
        await interaction.response.send_message(f"Available meme templates:\n{templates_list}")

def setup(bot):
    bot.add_cog(MemeGenerator(bot))
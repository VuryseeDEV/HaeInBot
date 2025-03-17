import nextcord
from nextcord.ext import commands
import sqlite3

class RulesCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "rules_data.db"
        self.setup_database()
        
    def setup_database(self):
        """Create necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rules_config (
                server_id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                footer TEXT,
                image_url TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rules_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT,
                label TEXT,
                content TEXT,
                FOREIGN KEY (server_id) REFERENCES rules_config (server_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_server_config(self, server_id):
        """Get the rules configuration for a server"""
        server_id = str(server_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the main config
        cursor.execute(
            "SELECT title, content, footer, image_url FROM rules_config WHERE server_id = ?", 
            (server_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return None
            
        config = {
            "title": result[0],
            "content": result[1],
            "footer": result[2],
            "image_url": result[3],
            "buttons": []
        }
        
        # Get the buttons
        cursor.execute(
            "SELECT label, content FROM rules_buttons WHERE server_id = ?",
            (server_id,)
        )
        
        buttons = cursor.fetchall()
        for button in buttons:
            config["buttons"].append({
                "label": button[0],
                "content": button[1]
            })
            
        conn.close()
        return config
    
    def save_server_config(self, server_id, title, content, footer, image_url=None):
        """Save the main rules configuration for a server"""
        server_id = str(server_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if config exists
        cursor.execute(
            "SELECT COUNT(*) FROM rules_config WHERE server_id = ?",
            (server_id,)
        )
        exists = cursor.fetchone()[0] > 0
        
        # Insert or update
        if exists:
            cursor.execute(
                "UPDATE rules_config SET title = ?, content = ?, footer = ?, image_url = ? WHERE server_id = ?",
                (title, content, footer, image_url, server_id)
            )
        else:
            cursor.execute(
                "INSERT INTO rules_config (server_id, title, content, footer, image_url) VALUES (?, ?, ?, ?, ?)",
                (server_id, title, content, footer, image_url)
            )
            
        conn.commit()
        conn.close()
    
    def add_button(self, server_id, label, content):
        """Add a button to the rules configuration"""
        server_id = str(server_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO rules_buttons (server_id, label, content) VALUES (?, ?, ?)",
            (server_id, label, content)
        )
        
        conn.commit()
        conn.close()
    
    def clear_buttons(self, server_id):
        """Remove all buttons for a server"""
        server_id = str(server_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM rules_buttons WHERE server_id = ?",
            (server_id,)
        )
        
        conn.commit()
        conn.close()
    
    def count_buttons(self, server_id):
        """Count buttons for a server"""
        server_id = str(server_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM rules_buttons WHERE server_id = ?",
            (server_id,)
        )
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def update_image_url(self, server_id, image_url):
        """Update the image URL for a server's rules"""
        server_id = str(server_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE rules_config SET image_url = ? WHERE server_id = ?",
            (image_url, server_id)
        )
        
        conn.commit()
        conn.close()
    
    @nextcord.slash_command(name="rules", description="Create or display rules with interactive buttons")
    async def rules(self, interaction: nextcord.Interaction):
        """Base command for rules functionality"""
        pass
        
    @rules.subcommand(name="create", description="Create a new rules embed with buttons")
    async def create_rules(self, interaction: nextcord.Interaction):
        """Create a new rules embed with custom buttons"""
        # Initial modal for the main embed content
        modal = RulesModal(cog=self, title="Create Rules Embed")
        
        # Send the modal
        await interaction.response.send_modal(modal)
    
    @rules.subcommand(name="preview", description="Preview your rules embed before posting")
    async def preview_rules(self, interaction: nextcord.Interaction):
        """Preview the rules embed before posting it"""
        server_id = str(interaction.guild_id)
        
        config = self.get_server_config(server_id)
        if not config:
            await interaction.response.send_message("No rules configuration found for this server. Use `/rules create` first.", ephemeral=True)
            return
        
        # Create the embed
        embed = self.build_embed_from_config(config)
        
        # Create the buttons
        view = RulesButtonView(config.get("buttons", []))
        
        await interaction.response.send_message("Rules Preview (Only you can see this):", embed=embed, view=view, ephemeral=True)
    
    @rules.subcommand(name="post", description="Post your rules embed to a channel")
    async def post_rules(
        self, 
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(
            name="channel",
            description="Channel to post the rules in",
            required=False
        )
    ):
        """Post the rules embed to the specified channel or current channel"""
        server_id = str(interaction.guild_id)
        
        config = self.get_server_config(server_id)
        if not config:
            await interaction.response.send_message("No rules configuration found for this server. Use `/rules create` first.", ephemeral=True)
            return
        
        # Use the specified channel or default to current channel
        target_channel = channel if channel and isinstance(channel, nextcord.TextChannel) else interaction.channel
        
        # Check permissions
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(f"I don't have permission to send messages in {target_channel.mention}!", ephemeral=True)
            return
        
        # Create the embed
        embed = self.build_embed_from_config(config)
        
        # Create the buttons
        view = RulesButtonView(config.get("buttons", []))
        
        await interaction.response.send_message(f"Posting rules to {target_channel.mention}...", ephemeral=True)
        await target_channel.send(embed=embed, view=view)
    
    @rules.subcommand(name="edit", description="Edit your existing rules configuration")
    async def edit_rules(self, interaction: nextcord.Interaction):
        """Edit the existing rules configuration"""
        server_id = str(interaction.guild_id)
        
        config = self.get_server_config(server_id)
        if not config:
            await interaction.response.send_message("No rules configuration found for this server. Use `/rules create` first.", ephemeral=True)
            return
        
        # Create modal with pre-filled values
        modal = RulesModal(
            cog=self,
            title="Edit Rules Embed",
            default_title=config.get("title", "Server Rules"),
            default_content=config.get("content", ""),
            default_footer=config.get("footer", ""),
            default_image=config.get("image_url", "")
        )
        
        await interaction.response.send_modal(modal)
    
    @rules.subcommand(name="set_image", description="Set an image URL for your rules embed")
    async def set_image(
        self,
        interaction: nextcord.Interaction,
        image_url: str = nextcord.SlashOption(
            name="image_url",
            description="URL of the image to display in the rules embed",
            required=True
        )
    ):
        """Set an image URL for the rules embed"""
        server_id = str(interaction.guild_id)
        
        config = self.get_server_config(server_id)
        if not config:
            await interaction.response.send_message("No rules configuration found for this server. Use `/rules create` first.", ephemeral=True)
            return
        
        # Update the image URL
        self.update_image_url(server_id, image_url)
        
        await interaction.response.send_message(f"Image URL set! Use `/rules preview` to see how it looks.", ephemeral=True)
    
    @rules.subcommand(name="add_button", description="Add a button to your rules embed")
    async def add_button_cmd(self, interaction: nextcord.Interaction):
        """Add a button to the rules embed"""
        server_id = str(interaction.guild_id)
        
        config = self.get_server_config(server_id)
        if not config:
            await interaction.response.send_message("No rules configuration found for this server. Use `/rules create` first.", ephemeral=True)
            return
        
        modal = ButtonModal(cog=self, title="Add Button")
        await interaction.response.send_modal(modal)
    
    @rules.subcommand(name="clear_buttons", description="Remove all buttons from your rules embed")
    async def clear_buttons_cmd(self, interaction: nextcord.Interaction):
        """Remove all buttons from the rules embed"""
        server_id = str(interaction.guild_id)
        
        config = self.get_server_config(server_id)
        if not config:
            await interaction.response.send_message("No rules configuration found for this server. Use `/rules create` first.", ephemeral=True)
            return
        
        # Remove all buttons
        self.clear_buttons(server_id)
        
        await interaction.response.send_message("All buttons have been removed from your rules embed.", ephemeral=True)
    
    def build_embed_from_config(self, config):
        """Build an embed using the configuration"""
        embed = nextcord.Embed(
            title=config.get("title", "Server Rules"),
            description=config.get("content", "No rules specified."),
            color=0x3498db  # Blue color
        )
        
        # Add image if available
        if config.get("image_url"):
            embed.set_image(url=config.get("image_url"))
            
        if config.get("footer"):
            embed.set_footer(text=config.get("footer"))
            
        return embed
    
    async def process_modal_submission(self, interaction, title, content, footer, image_url=None):
        """Process the modal submission for creating/editing rules"""
        server_id = str(interaction.guild_id)
        
        # Save the configuration
        self.save_server_config(server_id, title, content, footer, image_url)
        
        # Get the updated config
        config = self.get_server_config(server_id)
        
        # Send a confirmation
        embed = self.build_embed_from_config(config)
        
        await interaction.response.send_message(
            "Rules configuration saved! Use `/rules preview` to preview or `/rules post` to post it.\n"
            "You can add buttons with `/rules add_button` and set an image with `/rules set_image`.",
            embed=embed,
            ephemeral=True
        )
    
    async def process_button_submission(self, interaction, label, content):
        """Process the modal submission for adding a button"""
        server_id = str(interaction.guild_id)
        
        # Add the button
        self.add_button(server_id, label, content)
        
        # Get button count
        button_count = self.count_buttons(server_id)
        
        await interaction.response.send_message(
            f"Button added! You now have {button_count} button(s).\n"
            "Use `/rules preview` to see how it looks or `/rules post` to post the rules with buttons.",
            ephemeral=True
        )


class RulesModal(nextcord.ui.Modal):
    def __init__(self, cog, title, default_title=None, default_content=None, default_footer=None, default_image=None):
        super().__init__(title=title)
        
        # Store the cog reference
        self.cog = cog
        
        self.title_input = nextcord.ui.TextInput(
            label="Title",
            placeholder="Enter the title for your rules embed",
            required=True,
            max_length=256,
            default_value=default_title or "Server Rules"
        )
        self.add_item(self.title_input)
        
        self.content_input = nextcord.ui.TextInput(
            label="Content",
            placeholder="Enter the rules content here...",
            required=True,
            style=nextcord.TextInputStyle.paragraph,
            max_length=4000,
            default_value=default_content or ""
        )
        self.add_item(self.content_input)
        
        self.footer_input = nextcord.ui.TextInput(
            label="Footer (Optional)",
            placeholder="Enter footer text (optional)",
            required=False,
            max_length=2048,
            default_value=default_footer or ""
        )
        self.add_item(self.footer_input)
        
        self.image_input = nextcord.ui.TextInput(
            label="Image URL (Optional)",
            placeholder="Enter an image URL to display (optional)",
            required=False,
            max_length=2048,
            default_value=default_image or ""
        )
        self.add_item(self.image_input)
    
    async def callback(self, interaction: nextcord.Interaction):
        # Get the values from the inputs
        title = self.title_input.value
        content = self.content_input.value
        footer = self.footer_input.value
        image_url = self.image_input.value if self.image_input.value.strip() else None
        
        # Use the stored cog reference
        await self.cog.process_modal_submission(interaction, title, content, footer, image_url)


class ButtonModal(nextcord.ui.Modal):
    def __init__(self, cog, title):
        super().__init__(title=title)
        
        # Store the cog reference
        self.cog = cog
        
        self.label_input = nextcord.ui.TextInput(
            label="Button Label",
            placeholder="Enter the text to display on the button",
            required=True,
            max_length=80
        )
        self.add_item(self.label_input)
        
        self.content_input = nextcord.ui.TextInput(
            label="Button Response",
            placeholder="Enter the text to show when the button is clicked",
            required=True,
            style=nextcord.TextInputStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.content_input)
    
    async def callback(self, interaction: nextcord.Interaction):
        # Get the values from the inputs
        label = self.label_input.value
        content = self.content_input.value
        
        # Use the stored cog reference
        await self.cog.process_button_submission(interaction, label, content)


class RulesButtonView(nextcord.ui.View):
    def __init__(self, buttons):
        super().__init__(timeout=None)  # No timeout for buttons
        
        # Add buttons based on configuration
        for i, button_data in enumerate(buttons):
            # Create a button with the label
            button = nextcord.ui.Button(
                style=nextcord.ButtonStyle.secondary,
                label=button_data["label"],
                custom_id=f"rules_button_{i}"
            )
            
            # Set the callback
            button.callback = self.create_callback(button_data["content"])
            
            # Add to view
            self.add_item(button)
    
    def create_callback(self, content):
        """Create a callback for a button with specific content"""
        async def button_callback(interaction):
            await interaction.response.send_message(content, ephemeral=True)
        return button_callback


def setup(bot):
    bot.add_cog(RulesCommand(bot))
import nextcord
from nextcord.ext import commands
import random
import asyncio
import sqlite3
from typing import List, Dict, Tuple, Optional

class Card:
    def __init__(self, suit: str, value: str):
        self.suit = suit
        self.value = value
    
    def __str__(self) -> str:
        return f"{self.value}{self.suit}"
    
    def get_value(self) -> int:
        if self.value in ['J', 'Q', 'K']:
            return 10
        elif self.value == 'A':
            return 11  # ace is initially 11, will be adjusted if needed
        else:
            return int(self.value)

class BlackjackGame:
    def __init__(self, player_id: int, bet: int = 0, dealer_id: int = None):
        self.player_id = player_id
        self.dealer_id = dealer_id  #None means playing against bot, otherwise this is the user ID of the dealer player
        self.bet = bet
        self.deck = self._create_deck()
        self.player_hand: List[Card] = []
        self.dealer_hand: List[Card] = []
        self.game_status = "active"  # active, player_win, dealer_win, tie, player_bust, dealer_bust
        self.player_stood = False
        self.dealer_stood = False
        
        #  Deal initial cards
        self.player_hand.append(self._draw_card())
        self.dealer_hand.append(self._draw_card())
        self.player_hand.append(self._draw_card())
        self.dealer_hand.append(self._draw_card())
        
        #check for natural blackjack
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        if player_value == 21 and dealer_value == 21:
            self.game_status = "tie"
        elif player_value == 21:
            self.game_status = "player_blackjack"
        elif dealer_value == 21:
            self.game_status = "dealer_blackjack"
    
    def _create_deck(self) -> List[Card]:
        suits = ['♥', '♦', '♣', '♠']
        values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [Card(suit, value) for suit in suits for value in values]
        random.shuffle(deck)
        return deck
    
    def _draw_card(self) -> Card:
        return self.deck.pop()
    
    def calculate_hand_value(self, hand: List[Card]) -> int:
        value = sum(card.get_value() for card in hand)
        #Adjust for aces if needed
        aces = sum(1 for card in hand if card.value == 'A')
        while value > 21 and aces > 0:
            value -= 10  #Change an Ace from 11 to 1
            aces -= 1
        return value
    
    def player_hit(self) -> None:
        """Add a card to the player's hand"""
        self.player_hand.append(self._draw_card())
        player_value = self.calculate_hand_value(self.player_hand)
        
        if player_value > 21:
            self.game_status = "player_bust"
            self.player_stood = True
    
    def dealer_hit(self) -> None:
        """Add a card to the dealer's hand"""
        self.dealer_hand.append(self._draw_card())
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        if dealer_value > 21:
            self.game_status = "dealer_bust"
            self.dealer_stood = True
    
    def player_stand(self) -> None:
        """Player chooses to stand"""
        self.player_stood = True
        
        #If playing against bot, bot plays automatically
        if self.dealer_id is None:
            self.bot_dealer_play()
        
    def dealer_stand(self) -> None:
        """Dealer chooses to stand"""
        self.dealer_stood = True
        
        #Game ends when both have stood
        if self.player_stood and self.dealer_stood:
            self.determine_winner()
    
    def bot_dealer_play(self) -> None:
        """Execute bot dealer's turn according to standard rules"""
        #dealer must hit until they have at least 17
        while self.calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self._draw_card())
        
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        player_value = self.calculate_hand_value(self.player_hand)
        
        if dealer_value > 21:
            self.game_status = "dealer_bust"
        elif dealer_value > player_value:
            self.game_status = "dealer_win"
        elif player_value > dealer_value:
            self.game_status = "player_win"
        else:
            self.game_status = "tie"
    
    def determine_winner(self) -> None:
        """Determine the winner after both have stood"""
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        # If someone already busted, game is already decided
        if self.game_status in ["player_bust", "dealer_bust"]:
            return
            
        if player_value > dealer_value:
            self.game_status = "player_win"
        elif dealer_value > player_value:
            self.game_status = "dealer_win"
        else:
            self.game_status = "tie"
    
    def get_player_hand_str(self) -> str:
        return " ".join(str(card) for card in self.player_hand)
    
    def get_dealer_hand_str(self, hide_hole_card: bool = False) -> str:
        if hide_hole_card and len(self.dealer_hand) > 1 and self.dealer_id is None:
            # Only hide hole card when playing against bot
            return f"{str(self.dealer_hand[0])} ??"
        return " ".join(str(card) for card in self.dealer_hand)
    
    def get_status_message(self) -> str:
        if self.game_status == "player_bust":
            return "Player bust! Dealer wins!"
        elif self.game_status == "dealer_bust":
            return "Dealer bust! Player wins!"
        elif self.game_status == "player_win":
            return "Player wins!"
        elif self.game_status == "dealer_win":
            return "Dealer wins!"
        elif self.game_status == "tie":
            return "It's a tie!"
        elif self.game_status == "player_blackjack":
            return "Player has Blackjack and wins!"
        elif self.game_status == "dealer_blackjack":
            return "Dealer has Blackjack and wins!"
        else:
            return "Game in progress"
    
    def calculate_payout(self, for_player: bool = True) -> int:
        """Calculate payout based on game result"""
        if for_player:
            # Calculate payout for the player
            if self.game_status == "player_blackjack" and self.dealer_id is None:
                # Blackjack pays 3:2 (only when playing against bot)
                return int(self.bet * 1.5)
            elif self.game_status in ["player_win", "dealer_bust"]:
                # Regular win pays 1:1
                return self.bet
            elif self.game_status == "tie":
                # Tie returns the original bet
                return 0
            else:
                # Player loses
                return -self.bet
        else:
            # Calculate payout for the dealer (when it's a human player)
            if self.game_status in ["dealer_win", "player_bust"]:
                # Dealer wins
                return self.bet
            elif self.game_status == "tie":
                # Tie returns the original bet
                return 0
            else:
                # Dealer loses
                return -self.bet


class BlackjackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games: Dict[int, Dict[int, BlackjackGame]] = {}  # server_id -> {user_id: game}
        self.pending_invites: Dict[int, Dict[int, Dict]] = {}  # server_id -> {target_id: {sender_id, bet}}
        self.conn = sqlite3.connect('anigame.db')
        self.cursor = self.conn.cursor()
        self.min_bet = 10
        self.max_bet = 100000
    
    def cog_unload(self):
        """Close the database connection when the cog is unloaded"""
        if self.conn:
            self.conn.close()
    
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
    
    @nextcord.slash_command(name="blackjack", description="Play a game of Blackjack")
    async def blackjack(self, interaction: nextcord.Interaction):
        pass

    @blackjack.subcommand(name="play", description="Play a game of Blackjack")
    async def blackjack_play(self, interaction: nextcord.Interaction, 
                      bet: int = nextcord.SlashOption(
                          name="bet",
                          description="Amount to bet (min: 10, max: 100000)",
                          required=True,
                          min_value=10,
                          max_value=100000
                      ),
                      opponent: nextcord.Member = nextcord.SlashOption(
                          name="opponent",
                          description="Player to challenge (you'll be the dealer)",
                          required=False
                      )):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        # Check if user already has an active game in this server
        if server_id in self.active_games and user_id in self.active_games[server_id]:
            await interaction.response.send_message("You already have an active Blackjack game!", ephemeral=True)
            return
            
        # Check for pending invites
        if server_id in self.pending_invites and user_id in self.pending_invites[server_id]:
            await interaction.response.send_message("You already have a pending challenge! Cancel it first.", ephemeral=True)
            return
        
        # Check if user has enough credits
        balance = self.get_user_balance(user_id, server_id)
        if balance < bet:
            await interaction.response.send_message(f"You don't have enough credits! You need {bet} credits, but you only have {balance}.", ephemeral=True)
            return
            
        # If opponent is specified, send a challenge
        if opponent:
            # Don't allow challenging yourself
            if opponent.id == user_id:
                await interaction.response.send_message("You can't challenge yourself to a game!", ephemeral=True)
                return
                
            # Check if opponent already has an active game
            if server_id in self.active_games and opponent.id in self.active_games[server_id]:
                await interaction.response.send_message(f"{opponent.display_name} already has an active game!", ephemeral=True)
                return
                
            # Check if opponent already has a pending challenge
            if server_id in self.pending_invites and opponent.id in self.pending_invites[server_id]:
                await interaction.response.send_message(f"{opponent.display_name} already has a pending challenge!", ephemeral=True)
                return
                
            # Check if opponent has enough credits
            opponent_balance = self.get_user_balance(opponent.id, server_id)
            if opponent_balance < bet:
                await interaction.response.send_message(f"{opponent.display_name} doesn't have enough credits for this bet!", ephemeral=True)
                return
                
            # Store the pending invite
            if server_id not in self.pending_invites:
                self.pending_invites[server_id] = {}
            
            self.pending_invites[server_id][opponent.id] = {
                'sender_id': user_id,
                'bet': bet,
                'message_id': None
            }
            
            # Create challenge embed
            embed = nextcord.Embed(
                title="Blackjack Challenge",
                description=f"{interaction.user.mention} has challenged you to a game of Blackjack!",
                color=0x00ff00
            )
            embed.add_field(name="Bet Amount", value=f"{bet} credits", inline=True)
            embed.add_field(name="Your Balance", value=f"{opponent_balance} credits", inline=True)
            embed.add_field(name="Game Format", value=f"{interaction.user.display_name} will be the dealer, and you'll be the player.", inline=False)
            
            # Create accept/decline buttons
            view = nextcord.ui.View(timeout=120)  # 2 minute timeout
            
            accept_button = nextcord.ui.Button(label="Accept Challenge", style=nextcord.ButtonStyle.green)
            decline_button = nextcord.ui.Button(label="Decline", style=nextcord.ButtonStyle.red)
            
            async def accept_callback(button_interaction):
                if button_interaction.user.id != opponent.id:
                    await button_interaction.response.send_message("This challenge isn't for you to accept!", ephemeral=True)
                    return
                    
                # Check if the challenge is still valid
                if server_id not in self.pending_invites or opponent.id not in self.pending_invites[server_id]:
                    await button_interaction.response.send_message("This challenge is no longer valid!", ephemeral=True)
                    return
                
                # Recheck balances
                current_sender_balance = self.get_user_balance(user_id, server_id)
                current_opponent_balance = self.get_user_balance(opponent.id, server_id)
                
                if current_sender_balance < bet:
                    await button_interaction.response.send_message(
                        f"{interaction.user.display_name} no longer has enough credits for this challenge!",
                        ephemeral=False
                    )
                    # Clean up the invite
                    del self.pending_invites[server_id][opponent.id]
                    return
                    
                if current_opponent_balance < bet:
                    await button_interaction.response.send_message(
                        "You don't have enough credits for this challenge!",
                        ephemeral=True
                    )
                    #clean up the invite
                    del self.pending_invites[server_id][opponent.id]
                    return
                
                #Get invitation data and clean it up BEFORE creating the game
                del self.pending_invites[server_id][opponent.id]
                
                #Delete the original challenge message
                try:
                    original_message = button_interaction.message
                    await original_message.delete()
                except Exception as e:
                    print(f"Error deleting challenge message: {e}")
                    #Continue even if deletion fails
                
                #Deduct bets from both players
                self.update_user_balance(user_id, server_id, -bet)
                self.update_user_balance(opponent.id, server_id, -bet)
                
                #Start the PvP game
                if server_id not in self.active_games:
                    self.active_games[server_id] = {}
                
                # Create game with sender as dealer and opponent as player
                game = BlackjackGame(opponent.id, bet, user_id)  # Player ID is opponent, dealer ID is sender
                self.active_games[server_id][user_id] = game
                self.active_games[server_id][opponent.id] = game  # Both players reference the same game
                
                #Try to send dealer info via DM BEFORE responding to the interaction
                dealer_second_card = game.dealer_hand[1]
                try:
                    dealer_user = await self.bot.fetch_user(user_id)
                    await dealer_user.send(
                        f"🎰 **Blackjack Dealer Info**\n"
                        f"Your hole card (hidden from {opponent.display_name}) is: **{dealer_second_card}**\n"
                        f"Your full hand: {game.get_dealer_hand_str(False)} (Value: {game.calculate_hand_value(game.dealer_hand)})"
                    )
                except Exception as e:
                    print(f"Error sending dealer card DM: {e}")
                    # Continue even if DM fails
                
                # Create modified PvP game embed that hides dealer's second card from player view
                game_embed = self._create_pvp_game_embed(game, opponent, interaction.user, hide_dealer_hole=True)
                
                #Create pvP action buttons and add to bot view store for persistence
                action_row = self._create_pvp_action_buttons(opponent.id, user_id)  # Player is opponent, dealer is sender
                #add view to bot's view store for persistence (if needed)
                try:
                    self.bot.add_view(action_row)
                except Exception as e:
                    print(f"Error adding view to bot: {e}")
                
                # Handle natural blackjacks
                if game.game_status in ["player_blackjack", "dealer_blackjack", "tie"]:
                    # Game is over immediately with a natural blackjack
                    if game.game_status == "player_blackjack":
                        # Player (opponent) wins
                        self.update_user_balance(opponent.id, server_id, bet * 2)  # Return bet + dealer's bet
                        await button_interaction.response.send_message(
                            f"{opponent.mention} got Blackjack and won {bet} credits from {interaction.user.mention}!",
                            embed=game_embed
                        )
                    elif game.game_status == "dealer_blackjack":
                        # Dealer (sender) wins
                        self.update_user_balance(user_id, server_id, bet * 2)  # Return bet + player's bet
                        await button_interaction.response.send_message(
                            f"{interaction.user.mention} (dealer) got Blackjack and won {bet} credits from {opponent.mention}!",
                            embed=game_embed
                        )
                    else:  # Tie
                        # Return bets to both players
                        self.update_user_balance(user_id, server_id, bet)
                        self.update_user_balance(opponent.id, server_id, bet)
                        await button_interaction.response.send_message(
                            f"Both players got Blackjack! It's a tie, all bets returned.",
                            embed=game_embed
                        )
                    
                    # Clean up the game
                    del self.active_games[server_id][user_id]
                    del self.active_games[server_id][opponent.id]
                    return
                
                # IMPORTANT: Send game message with the action buttons attached
                await button_interaction.response.send_message(
                    f"Game on! {opponent.mention} (player) vs {interaction.user.mention} (dealer) for {bet} credits each!",
                    embed=game_embed,
                    view=action_row  # Make sure to pass the view here
                )
            
            async def decline_callback(button_interaction):
                if button_interaction.user.id != opponent.id:
                    await button_interaction.response.send_message("This challenge isn't for you to decline!", ephemeral=True)
                    return
                
                # Clean up invite
                if server_id in self.pending_invites and opponent.id in self.pending_invites[server_id]:
                    del self.pending_invites[server_id][opponent.id]
                
                # Delete the original challenge message
                try:
                    original_message = button_interaction.message
                    await original_message.delete()
                except Exception as e:
                    print(f"Error deleting challenge message: {e}")
                    # Continue even if deletion fails
                
                # Send decline message
                declined_embed = nextcord.Embed(
                    title="Challenge Declined",
                    description=f"{opponent.mention} has declined the blackjack challenge from {interaction.user.mention}.",
                    color=0xFF0000
                )
                
                await button_interaction.response.send_message(
                    f"Challenge declined by {opponent.mention}",
                    embed=declined_embed
                )
            
            accept_button.callback = accept_callback
            decline_button.callback = decline_callback
            
            view.add_item(accept_button)
            view.add_item(decline_button)
            
            await interaction.response.send_message(
                f"{opponent.mention}, you've been challenged to a game of Blackjack!",
                embed=embed,
                view=view
            )
            return
            
        # If no opponent specified, play against the dealer (bot)
        # Deduct bet amount from user balance
        self.update_user_balance(user_id, server_id, -bet)
        
        # Create a new game for the user
        if server_id not in self.active_games:
            self.active_games[server_id] = {}
        
        game = BlackjackGame(user_id, bet)  # No dealer_id means playing against bot
        self.active_games[server_id][user_id] = game
        
        # Create the initial game embed
        embed = self._create_game_embed(game, True)
        
        # Handle natural blackjacks
        if game.game_status in ["player_blackjack", "dealer_blackjack", "tie"]:
            # Game is over immediately with a natural blackjack
            embed = self._create_game_embed(game, False)
            
            # Process payout
            payout = game.calculate_payout()
            new_balance = self.update_user_balance(user_id, server_id, payout + bet)  # Return the bet + any winnings
            
            embed.add_field(name="Payout", value=f"{payout} credits", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Remove the game after a short delay
            await asyncio.sleep(2)
            del self.active_games[server_id][user_id]
            return
        
        # Create action buttons
        action_row = self._create_action_buttons()
        
        await interaction.response.send_message(embed=embed, view=action_row)

    @blackjack.subcommand(name="rules", description="Learn how to play Blackjack")
    async def blackjack_rules(self, interaction: nextcord.Interaction):
        # Create an embed with the rules
        embed = nextcord.Embed(
            title="Blackjack Rules & How to Play",
            description="Welcome to Blackjack! Here's how to play in our server.",
            color=0x00BFFF
        )
        
        # Basic rules
        embed.add_field(
            name="🎯 Game Objective",
            value="Beat the dealer by getting a hand value as close to 21 as possible without going over.",
            inline=False
        )
        
        # Card values
        embed.add_field(
            name="🃏 Card Values",
            value="• Number cards (2-10): Face value\n"
                  "• Face cards (J, Q, K): 10 points\n"
                  "• Ace (A): 11 points or 1 point (whichever benefits you more)",
            inline=False
        )
        
        # Single player mode
        embed.add_field(
            name="🤖 Playing Against Bot",
            value="**Command:** `/blackjack play bet:[amount]`\n\n"
                  "1. Place a bet (10-1000 credits)\n"
                  "2. Get dealt 2 cards, dealer gets 2 cards (one face down)\n"
                  "3. Choose to **Hit** (get another card) or **Stand** (keep current hand)\n"
                  "4. Dealer will hit until they have at least 17\n"
                  "5. Closest to 21 without busting wins\n"
                  "6. Blackjack (21 with first two cards) pays 3:2",
            inline=False
        )
        
        # PvP mode
        embed.add_field(
            name="👥 Playing Against Others",
            value="**Command:** `/blackjack play bet:[amount] opponent:[@user]`\n\n"
                  "1. Challenge another player, specifying the bet amount\n"
                  "2. The challenger becomes the dealer\n"
                  "3. The opponent must accept the challenge\n"
                  "4. Player draws first, then stands when ready\n"
                  "5. Dealer plays after player stands\n"
                  "6. Same rules apply for winning",
            inline=False
        )
        
        # Special game states
        embed.add_field(
            name="💰 Winning & Payouts",
            value="• Regular win: 1:1 (double your bet)\n"
                  "• Natural Blackjack vs Bot: 3:2 (1.5x your bet)\n"
                  "• Tie: Bets returned to both players\n"
                  "• Lose: Forfeit your bet",
            inline=False
        )
        
        # Buttons explanation
        embed.add_field(
            name="🎮 Game Controls",
            value="• **Hit:** Draw another card\n"
                  "• **Stand:** End your turn with current hand\n"
                  "• **Double Down:** (vs Bot only) Double your bet and get exactly one more card\n"
                  "• **Cancel Game:** (PvP only) End the game early and return bets",
            inline=False
        )
        
        # Tips
        embed.add_field(
            name="💡 Tips",
            value="• Stand on 17 or higher\n"
                  "• Always hit on 11 or lower\n"
                  "• Remember the dealer must hit until 17\n"
                  "• The dealer's hole card gives them an advantage",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    def _create_game_embed(self, game: BlackjackGame, hide_dealer_card: bool = False) -> nextcord.Embed:
        embed = nextcord.Embed(title="Blackjack vs Dealer Bot", color=0x00ff00)
        
        # Show dealer's hand (hide the hole card if game is still active)
        dealer_hand = game.get_dealer_hand_str(hide_dealer_card)
        dealer_value = "?" if hide_dealer_card else game.calculate_hand_value(game.dealer_hand)
        embed.add_field(name=f"Dealer's Hand ({dealer_value})", value=dealer_hand, inline=False)
        
        # Show player's hand
        player_value = game.calculate_hand_value(game.player_hand)
        embed.add_field(name=f"Your Hand ({player_value})", value=game.get_player_hand_str(), inline=False)
        
        # Show bet amount
        embed.add_field(name="Your Bet", value=f"{game.bet} credits", inline=True)
        
        # Show game status if game is over
        if game.game_status != "active":
            embed.add_field(name="Result", value=game.get_status_message(), inline=False)
        
        return embed
        
    def _create_pvp_game_embed(self, game: BlackjackGame, player: nextcord.Member, dealer: nextcord.Member, hide_dealer_hole: bool = False) -> nextcord.Embed:
        """Create an embed for PvP games showing hands, hiding dealer's hole card from public view"""
        embed = nextcord.Embed(title=f"Blackjack: {player.display_name} (Player) vs {dealer.display_name} (Dealer)", color=0x00ff00)
        
        # Show player hands
        player_value = game.calculate_hand_value(game.player_hand)
        dealer_value = "?" if hide_dealer_hole else game.calculate_hand_value(game.dealer_hand)
        
        # Add player status
        player_status = "Stood" if game.player_stood else "Playing"
        dealer_status = "Stood" if game.dealer_stood else "Waiting"
        
        embed.add_field(
            name=f"{player.display_name}'s Hand ({player_value}) - {player_status}",
            value=game.get_player_hand_str(),
            inline=False
        )
        
        # Show dealer's hand with hole card hidden in public view
        if hide_dealer_hole and len(game.dealer_hand) > 1:
            dealer_hand_str = f"{str(game.dealer_hand[0])} ??"
        else:
            dealer_hand_str = game.get_dealer_hand_str()
            
        embed.add_field(
            name=f"{dealer.display_name}'s Hand ({dealer_value}) - {dealer_status}",
            value=dealer_hand_str,
            inline=False
        )
        
        # Show bet amount
        embed.add_field(name="Bet Amount", value=f"{game.bet} credits each", inline=True)
        
        # Show whose turn it is
        if game.game_status == "active":
            if not game.player_stood:
                current_turn = f"{player.display_name}'s turn (Player)"
            else:
                current_turn = f"{dealer.display_name}'s turn (Dealer)"
            embed.add_field(name="Current Turn", value=current_turn, inline=True)
        
        # Show game status if game is over
        if game.game_status != "active":
            embed.add_field(name="Result", value=game.get_status_message(), inline=False)
        
        return embed
    def _create_action_buttons(self) -> nextcord.ui.View:
        class BlackjackView(nextcord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=180)  # 3 minute timeout
                self.cog = cog
            
            @nextcord.ui.button(label="Hit", style=nextcord.ButtonStyle.primary)
            async def hit_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
                await self.cog._handle_hit(interaction)
            
            @nextcord.ui.button(label="Stand", style=nextcord.ButtonStyle.secondary)
            async def stand_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
                await self.cog._handle_stand(interaction)
            
            @nextcord.ui.button(label="Double Down", style=nextcord.ButtonStyle.success)
            async def double_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
                await self.cog._handle_double_down(interaction)
        
        return BlackjackView(self)
    
    async def _handle_hit(self, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        # Ensure the user has an active game
        if server_id not in self.active_games or user_id not in self.active_games[server_id]:
            await interaction.response.send_message("You don't have an active Blackjack game!", ephemeral=True)
            return
        
        game = self.active_games[server_id][user_id]
        
        # Check if player has already stood
        if game.player_stood:
            await interaction.response.send_message("You've already stood. You can't hit now.", ephemeral=True)
            return
        
        # In a regular game against bot, the user is the player
        game.player_hit()
        
        # Check if player busted
        if game.game_status == "player_bust":
            embed = self._create_game_embed(game, False)
            
            # Update user balance (they already lost their bet when starting)
            new_balance = self.get_user_balance(user_id, server_id)
            embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Remove the game
            del self.active_games[server_id][user_id]
        else:
            # Continue the game - player can hit again
            embed = self._create_game_embed(game, True)
            await interaction.response.edit_message(embed=embed)

    async def _handle_stand(self, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        # Ensure the user has an active game
        if server_id not in self.active_games or user_id not in self.active_games[server_id]:
            await interaction.response.send_message("You don't have an active Blackjack game!", ephemeral=True)
            return
        
        game = self.active_games[server_id][user_id]
        
        # In a regular game against bot, the user is the player
        game.player_stand()
        
        # Bot dealer plays automatically
        
        # Determine payout
        payout = game.calculate_payout()
        new_balance = self.update_user_balance(user_id, server_id, payout + game.bet)  # Return the bet + any winnings
        
        # Show final game state
        embed = self._create_game_embed(game, False)
        embed.add_field(name="Payout", value=f"{payout} credits", inline=True)
        embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Remove the game
        del self.active_games[server_id][user_id]

    async def _handle_double_down(self, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        # Ensure the user has an active game
        if server_id not in self.active_games or user_id not in self.active_games[server_id]:
            await interaction.response.send_message("You don't have an active Blackjack game!", ephemeral=True)
            return
        
        game = self.active_games[server_id][user_id]
        
        #Check if player has already stood
        if game.player_stood:
            await interaction.response.send_message("You've already stood. You can't double down now.", ephemeral=True)
            return
        
        # Check if player has more than 2 cards (double down only allowed on initial hand)
        if len(game.player_hand) > 2:
            await interaction.response.send_message("You can only double down on your initial hand.", ephemeral=True)
            return
        
        # Check if user has enough credits to double down
        balance = self.get_user_balance(user_id, server_id)
        if balance < game.bet:
            await interaction.response.send_message(f"You don't have enough credits to double down! You need {game.bet} more credits.", ephemeral=True)
            return
        
        # Deduct the additional bet
        self.update_user_balance(user_id, server_id, -game.bet)
        game.bet *= 2  # Double the bet
        
        # Give player exactly one more card then stand
        game.player_hit()
        game.player_stand()
        
        # Determine payout
        payout = game.calculate_payout()
        new_balance = self.update_user_balance(user_id, server_id, payout + game.bet)  # Return the bet + any winnings
        
        # Show final game state
        embed = self._create_game_embed(game, False)
        embed.add_field(name="Double Down", value="You doubled your bet and received one card.", inline=False)
        embed.add_field(name="Payout", value=f"{payout} credits", inline=True)
        embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Remove the game
        del self.active_games[server_id][user_id]

    async def _handle_pvp_hit(self, interaction: nextcord.Interaction, player_id: int, dealer_id: int):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        # Ensure the user is part of this game
        if server_id not in self.active_games or (user_id != player_id and user_id != dealer_id):
            await interaction.response.send_message("You aren't part of this game!", ephemeral=True)
            return
        
        game = self.active_games[server_id][player_id]  # Same game object for both players
        
        # Check which player is trying to hit
        if user_id == player_id:
            #Player wants to hit
            if game.player_stood:
                await interaction.response.send_message("You've already stood. You can't hit now.", ephemeral=True)
                return
                
            #Execute the hit
            game.player_hit()
        elif user_id == dealer_id:
            # Dealer wants to hit
            if not game.player_stood:
                await interaction.response.send_message("You can't play until the player has stood.", ephemeral=True)
                return
                
            if game.dealer_stood:
                await interaction.response.send_message("You've already stood. You can't hit now.", ephemeral=True)
                return
                
            # Execute the hit
            game.dealer_hit()
        else:
            await interaction.response.send_message("You aren't part of this game!", ephemeral=True)
            return
        
        # Get the players
        player = await self.bot.fetch_user(player_id)
        dealer = await self.bot.fetch_user(dealer_id)
        
        # Check if the current player busted
        if game.game_status in ["player_bust", "dealer_bust"]:
            # Game over, someone busted
            embed = self._create_pvp_game_embed(game, player, dealer, hide_dealer_hole=False)  # Show all cards now
            
            # Determine winner and update balances
            if game.game_status == "player_bust":
                # Dealer wins
                self.update_user_balance(dealer_id, server_id, game.bet * 2)  # Return bet + player's bet
                winner = dealer.display_name
                loser = player.display_name
            else:  # dealer_bust
                # Player wins
                self.update_user_balance(player_id, server_id, game.bet * 2)  # Return bet + dealer's bet
                winner = player.display_name
                loser = dealer.display_name
            
            embed.add_field(name="Result", value=f"{winner} wins {game.bet} credits from {loser}!", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Clean up the game
            del self.active_games[server_id][player_id]
            del self.active_games[server_id][dealer_id]
        else:
            #Update the game display
            hide_hole = not game.player_stood  # Only reveal hole card if player has stood
            embed = self._create_pvp_game_embed(game, player, dealer, hide_dealer_hole=hide_hole)
            await interaction.response.edit_message(embed=embed)
            
            #If dealer just drew a card, send them a DM with their card info
            if user_id == dealer_id:
                try:
                    #Send DM to dealer about their new card after responding to interaction
                    dealer_hand_value = game.calculate_hand_value(game.dealer_hand)
                    await dealer.send(
                        f"🎰 **Blackjack Update**\n"
                        f"\nYou drew: **{game.dealer_hand[-1]}**\n"
                        f"\nYour full hand: {game.get_dealer_hand_str(False)} (Value: {dealer_hand_value})"
                    )
                except Exception as e:
                    print(f"Error sending dealer card DM: {e}")
                    #If DM fails, game still continues

    async def _handle_pvp_stand(self, interaction: nextcord.Interaction, player_id: int, dealer_id: int):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        #ensure the user is part of this game
        if server_id not in self.active_games or (user_id != player_id and user_id != dealer_id):
            await interaction.response.send_message("You aren't part of this game!", ephemeral=True)
            return
        
        game = self.active_games[server_id][player_id]  # Same game object for both players
        
        #Check which player is trying to stand
        if user_id == player_id:
            #Player wants to stand
            if game.player_stood:
                await interaction.response.send_message("You've already stood.", ephemeral=True)
                return
            
            #Exec the stand
            game.player_stand()
        elif user_id == dealer_id:
            # Dealer wants to stand
            if not game.player_stood:
                await interaction.response.send_message("You can't play until the player has stood.", ephemeral=True)
                return
                
            if game.dealer_stood:
                await interaction.response.send_message("You've already stood.", ephemeral=True)
                return
                
            #Exec the stand
            game.dealer_stand()
        else:
            await interaction.response.send_message("You aren't part of this game!", ephemeral=True)
            return
                
        #Get the players
        player = await self.bot.fetch_user(player_id)
        dealer = await self.bot.fetch_user(dealer_id)
        
        #heck if both players have stood (game over)
        if game.player_stood and game.dealer_stood:
            #Game over, determine winner
            game.determine_winner()
            
            # Create final embed showing all cards
            embed = self._create_pvp_game_embed(game, player, dealer, hide_dealer_hole=False)
            
            # Update balances based on game result
            if game.game_status == "player_win":
                # Player wins
                self.update_user_balance(player_id, server_id, game.bet * 2)  # Return bet + dealer's bet
                winner = player.display_name
                loser = dealer.display_name
            elif game.game_status == "dealer_win":
                #dealer wins
                self.update_user_balance(dealer_id, server_id, game.bet * 2)  # Return bet + player's bet
                winner = dealer.display_name
                loser = player.display_name
            else:  # tie
                #Return bets to both players
                self.update_user_balance(player_id, server_id, game.bet)
                self.update_user_balance(dealer_id, server_id, game.bet)
                winner = None
            
            if winner:
                embed.add_field(name="Result", value=f"{winner} wins {game.bet} credits from {loser}!", inline=False)
            else:
                embed.add_field(name="Result", value="It's a tie! All bets returned.", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            #Clean up the game
            del self.active_games[server_id][player_id]
            del self.active_games[server_id][dealer_id]
        else:
            #Update the game display
            hide_hole = not game.player_stood  # Only reveal hole card if player has stood
            embed = self._create_pvp_game_embed(game, player, dealer, hide_dealer_hole=hide_hole)
            await interaction.response.edit_message(embed=embed)

    async def _handle_pvp_cancel(self, interaction: nextcord.Interaction, player_id: int, dealer_id: int):
        user_id = interaction.user.id
        server_id = interaction.guild.id
        
        #Only allow the two players to cancel
        if user_id != player_id and user_id != dealer_id:
            await interaction.response.send_message("You aren't part of this game!", ephemeral=True)
            return
        
        #ensure the game exists
        if server_id not in self.active_games or player_id not in self.active_games[server_id]:
            await interaction.response.send_message("This game no longer exists!", ephemeral=True)
            return
            
        game = self.active_games[server_id][player_id]
        
        #Return bets to both players
        self.update_user_balance(player_id, server_id, game.bet)
        self.update_user_balance(dealer_id, server_id, game.bet)
        
        #Get the players
        player = await self.bot.fetch_user(player_id)
        dealer = await self.bot.fetch_user(dealer_id)
        
        #Create cancellation embed
        embed = nextcord.Embed(
            title="Game Cancelled",
            description=f"The Blackjack game between {player.display_name} and {dealer.display_name} has been cancelled.",
            color=0xFF0000
        )
        embed.add_field(name="Refund", value=f"Both players have been refunded {game.bet} credits.", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        #Clean up the game
        del self.active_games[server_id][player_id]
        del self.active_games[server_id][dealer_id]
    def _create_pvp_action_buttons(self, player_id: int, dealer_id: int) -> nextcord.ui.View:
        class PvPBlackjackView(nextcord.ui.View):
            def __init__(self, cog, player_id, dealer_id):
                super().__init__(timeout=300)  #5 min timeout
                self.cog = cog
                self.player_id = player_id
                self.dealer_id = dealer_id
            
            @nextcord.ui.button(label="Hit", style=nextcord.ButtonStyle.primary)
            async def hit_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
                await self.cog._handle_pvp_hit(interaction, self.player_id, self.dealer_id)
            
            @nextcord.ui.button(label="Stand", style=nextcord.ButtonStyle.secondary)
            async def stand_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
                await self.cog._handle_pvp_stand(interaction, self.player_id, self.dealer_id)
            
            @nextcord.ui.button(label="Cancel Game", style=nextcord.ButtonStyle.danger)
            async def cancel_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
                await self.cog._handle_pvp_cancel(interaction, self.player_id, self.dealer_id)
        
        view = PvPBlackjackView(self, player_id, dealer_id)
        return view
    def _create_pvp_game_embed(self, game: BlackjackGame, player: nextcord.Member, dealer: nextcord.Member, hide_dealer_hole: bool = False) -> nextcord.Embed:
        """Create an embed for PvP games showing hands, hiding dealer's hole card from public view"""
        embed = nextcord.Embed(title=f"Blackjack: {player.display_name} (Player) vs {dealer.display_name} (Dealer)", color=0x00ff00)
        
        #Show player hands
        player_value = game.calculate_hand_value(game.player_hand)
        dealer_value = "?" if hide_dealer_hole else game.calculate_hand_value(game.dealer_hand)
        
        #Add player status
        player_status = "Stood" if game.player_stood else "Playing"
        dealer_status = "Stood" if game.dealer_stood else "Waiting"
        
        embed.add_field(
            name=f"{player.display_name}'s Hand ({player_value}) - {player_status}",
            value=game.get_player_hand_str(),
            inline=False
        )
        
        #show dealer's hand with hole card hidden in public view
        if hide_dealer_hole and len(game.dealer_hand) > 1:
            dealer_hand_str = f"{str(game.dealer_hand[0])} ??"
        else:
            dealer_hand_str = game.get_dealer_hand_str()
            
        embed.add_field(
            name=f"{dealer.display_name}'s Hand ({dealer_value}) - {dealer_status}",
            value=dealer_hand_str,
            inline=False
        )
        
        # Show bet amount
        embed.add_field(name="Bet Amount", value=f"{game.bet} credits each", inline=True)
        
        # Show whose turn it is
        if game.game_status == "active":
            if not game.player_stood:
                current_turn = f"{player.display_name}'s turn (Player)"
            else:
                current_turn = f"{dealer.display_name}'s turn (Dealer)"
            embed.add_field(name="Current Turn", value=current_turn, inline=True)
        
        # Show game status if game is over
        if game.game_status != "active":
            embed.add_field(name="Result", value=game.get_status_message(), inline=False)
        
        return embed
def setup(bot):
    bot.add_cog(BlackjackCog(bot))
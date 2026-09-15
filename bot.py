import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import os
from flask import Flask
from threading import Thread

# --- Web Server to trick Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()
# ----------------------------------

# --- Channel Settings ---
WELCOME_CHANNEL_ID = 1541358114538913994   # Welcome Channel
GIVEAWAYS_CHANNEL_ID = 1541314936070742068 # Giveaways Channel (Kept for reference, though slash command works anywhere)
YOUTUBE_CHANNEL_ID = 1539906472169832559   # YouTube Notifications Channel

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for Welcome messages
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Start the YouTube notification background task
    if not youtube_notification_task.is_running():
        youtube_notification_task.start()

# Welcome Message Event
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"Welcome to the server, {member.mention}! We are glad to have you here. 🎉")

# --- Background Tasks (YouTube) ---
@tasks.loop(hours=24) # Runs every 24 hours (you can adjust this later)
async def youtube_notification_task():
    channel = bot.get_channel(YOUTUBE_CHANNEL_ID)
    if channel:
        # You can add your actual YouTube checking logic here later
        # await channel.send("Check out the new YouTube video!")
        pass

@youtube_notification_task.before_loop
async def before_youtube_task():
    await bot.wait_until_ready()

# --- Giveaway System ---
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = set()

    @discord.ui.button(label="Enter Giveaway 🎉", style=discord.ButtonStyle.green, custom_id="gw_enter")
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            await interaction.response.send_message("You are already in the giveaway!", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            await interaction.response.send_message("You entered the giveaway successfully!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="gw_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            self.participants.remove(interaction.user.id)
            await interaction.response.send_message("You left the giveaway.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not in the giveaway.", ephemeral=True)

# Slash Command for Giveaway
@bot.tree.command(name="giveaway", description="Start a giveaway in this channel")
@app_commands.describe(prize="What is the prize?", duration="Duration in seconds")
async def start_giveaway(interaction: discord.Interaction, prize: str, duration: int):
    # Admin check
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need admin permissions to start a giveaway.", ephemeral=True)
        return
    
    view = GiveawayView()
    
    # Ephemeral confirmation (Only you see this message)
    await interaction.response.send_message(f"Starting giveaway for '{prize}' in this channel...", ephemeral=True)
    
    # Public announcement in the channel
    msg = await interaction.channel.send(f"🎉 **GIVEAWAY** 🎉\n**Prize:** {prize}\nEnds in {duration} seconds!", view=view)
    
    await asyncio.sleep(duration)
    
    # Giveaway ends
    if len(view.participants) == 0:
        await msg.reply("Giveaway ended, but nobody entered. 😢")
    else:
        winner_id = random.choice(list(view.participants))
        await msg.reply(f"Congratulations <@{winner_id}>! You won **{prize}**! 🎉")

# ----------------------------------
# Secure Token Execution
TOKEN = os.getenv('TOKEN')

if __name__ == "__main__":
    bot.run(TOKEN)

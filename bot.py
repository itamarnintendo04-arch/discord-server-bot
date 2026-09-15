import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import os
import re
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
WELCOME_CHANNEL_ID = 1541358114538913994   
YOUTUBE_CHANNEL_ID = 1539906472169832559   

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- Helper Function: Parse Time ---
def parse_duration(duration_str: str) -> int:
    duration_str = duration_str.upper()
    if duration_str.endswith('MO'):
        return int(duration_str[:-2]) * 30 * 24 * 60 * 60
    elif duration_str.endswith('M'):
        return int(duration_str[:-1]) * 60
    elif duration_str.endswith('H'):
        return int(duration_str[:-1]) * 60 * 60
    elif duration_str.endswith('D'):
        return int(duration_str[:-1]) * 24 * 60 * 60
    else:
        return int(duration_str)

# --- Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    if not youtube_notification_task.is_running():
        youtube_notification_task.start()

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"Welcome to the server, {member.mention}! We are glad to have you here. 🎉")

# --- Background Tasks ---
@tasks.loop(hours=24)
async def youtube_notification_task():
    channel = bot.get_channel(YOUTUBE_CHANNEL_ID)
    if channel:
        pass 

@youtube_notification_task.before_loop
async def before_youtube_task():
    await bot.wait_until_ready()


# ==========================================
#         DYNAMIC HELP COMMAND
# ==========================================

@bot.tree.command(name="help", description="Show all available bot commands")
async def help_command(interaction: discord.Interaction):
    # Base help text for everyone
    help_text = (
        "🤖 **Public Bot Commands:**\n\n"
        "`/ping` - Check if the bot is alive and its latency.\n"
        "`/serverinfo` - Display information about this server.\n"
    )

    # If the user is an admin, add the SERVER TEAM section dynamically!
    if interaction.user.guild_permissions.administrator:
        help_text += (
            "\n🛡️ **SERVER TEAM (Admin Commands):**\n\n"
            "`/giveaway [prize] [duration] [winners]` - Start a giveaway.\n"
            "`/clear [amount]` - Delete multiple messages in the channel.\n"
            "`/modpanel` - Open the admin control buttons."
        )

    await interaction.response.send_message(help_text, ephemeral=True)


# ==========================================
#         PUBLIC COMMANDS
# ==========================================

@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping_command(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is {latency}ms.", ephemeral=True)

@bot.tree.command(name="serverinfo", description="Get information about the server")
async def serverinfo_command(interaction: discord.Interaction):
    guild = interaction.guild
    info = (
        f"**Server Name:** {guild.name}\n"
        f"**Total Members:** {guild.member_count}\n"
        f"**Created On:** {guild.created_at.strftime('%Y-%m-%d')}"
    )
    await interaction.response.send_message(info, ephemeral=True)


# ==========================================
#         ADMIN COMMANDS (Staff Only)
# ==========================================

@bot.tree.command(name="clear", description="Clear multiple messages (Admin only)")
@app_commands.describe(amount="How many messages to delete?")
async def clear_command(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Successfully deleted {len(deleted)} messages.", ephemeral=True)


# --- Admin Buttons Panel ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clear 5 Messages 🧹", style=discord.ButtonStyle.red, custom_id="admin_clear_5")
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 **Access Denied:** You cannot use admin buttons!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=5)
        await interaction.followup.send("Deleted 5 messages via Admin Panel.", ephemeral=True)

@bot.tree.command(name="modpanel", description="Open the admin control panel (Admin only)")
async def modpanel_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    
    view = AdminPanelView()
    await interaction.response.send_message("🛠️ **Admin Control Panel:**\n*Only admins can click these buttons.*", view=view, ephemeral=True)


# ==========================================
#             GIVEAWAY SYSTEM
# ==========================================

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = set()

    def update_button_label(self):
        for child in self.children:
            if child.custom_id == "gw_enter":
                child.label = f"Enter Giveaway 🎉 ({len(self.participants)})"
                break

    @discord.ui.button(label="Enter Giveaway 🎉 (0)", style=discord.ButtonStyle.green, custom_id="gw_enter")
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            await interaction.response.send_message("You are already in the giveaway!", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            self.update_button_label()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("You entered the giveaway successfully!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="gw_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            self.participants.remove(interaction.user.id)
            self.update_button_label()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("You left the giveaway.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not in the giveaway.", ephemeral=True)

@bot.tree.command(name="giveaway", description="Start a giveaway in this channel (Admin only)")
@app_commands.describe(
    prize="What is the prize?", 
    duration="Format: 5M (minutes), 2H (hours), 1D (days), 1MO (months)",
    winners="Number of winners"
)
async def start_giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    
    try:
        duration_seconds = parse_duration(duration)
    except Exception:
        await interaction.response.send_message("Invalid duration format! Use M, H, D, or MO.", ephemeral=True)
        return

    view = GiveawayView()
    await interaction.response.send_message(f"Starting giveaway for '{prize}' (Winners: {winners}, Time: {duration})...", ephemeral=True)
    
    msg = await interaction.channel.send(
        f"🎉 **GIVEAWAY** 🎉\n**Prize:** {prize}\n**Winners:** {winners}\nEnds in **{duration}**!", 
        view=view
    )
    
    await asyncio.sleep(duration_seconds)
    
    if len(view.participants) == 0:
        await msg.reply("Giveaway ended, but nobody entered. 😢")
    else:
        actual_winners_count = min(winners, len(view.participants))
        chosen_winners = random.sample(list(view.participants), actual_winners_count)
        mentions = ", ".join(f"<@{w}>" for w in chosen_winners)
        await msg.reply(f"Congratulations {mentions}! You won **{prize}**! 🎉")

# ----------------------------------
# Secure Token Execution
TOKEN = os.getenv('TOKEN')

if __name__ == "__main__":
    bot.run(TOKEN)

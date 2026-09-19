import discord
from discord.ext import commands
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
    return "Giveaway Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()
# ----------------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- Helper Function ---
def parse_duration(duration_str: str) -> int:
    duration_str = duration_str.upper()
    if duration_str.endswith('MO'): return int(duration_str[:-2]) * 30 * 24 * 60 * 60
    elif duration_str.endswith('M'): return int(duration_str[:-1]) * 60
    elif duration_str.endswith('H'): return int(duration_str[:-1]) * 60 * 60
    elif duration_str.endswith('D'): return int(duration_str[:-1]) * 24 * 60 * 60
    else: return int(duration_str)

# --- Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"ברוך הבא לשרת, {member.mention}! 🎉 שמחים שאתה כאן.")

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"ביי ביי {member.name}... 😢 נתגעגע.")

# ==========================================
#         ADVANCED GIVEAWAY SYSTEM
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
            await interaction.response.send_message("You are already in!", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            self.update_button_label()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Entered successfully!", ephemeral=True)

class FastGiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claimed = False

    @discord.ui.button(label="CLAIM FIRST!", style=discord.ButtonStyle.green, custom_id="gw_fast")
    async def fast_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed: return await interaction.response.send_message("Too late! Someone already claimed it.", ephemeral=True)
        self.claimed = True
        button.disabled = True
        button.label = "CLAIMED!"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"⚡ 🎉 {interaction.user.mention} won the **Fast Giveaway**! 🎉 ⚡")

# יצירת קבוצת פקודות בשביל ההפרדה בין fast ל-random
giveaway_group = app_commands.Group(name="giveaway", description="Giveaway system commands")

@giveaway_group.command(name="random", description="Start a normal giveaway with all settings")
@app_commands.describe(prize="Prize name", duration="Duration (e.g. 5M, 2H)", winners="Number of winners", hosted_by="Who is hosting this? (Optional)")
async def giveaway_random(interaction: discord.Interaction, prize: str, duration: str, winners: int, hosted_by: discord.Member = None):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    
    try: 
        duration_seconds = parse_duration(duration)
    except Exception: 
        return await interaction.response.send_message("Invalid duration format! Use M, H, D, or MO.", ephemeral=True)

    # אם לא נבחר משתמש ספציפי בשדה, המארח הוא מי שהפעיל את הפקודה
    host = hosted_by if hosted_by else interaction.user
    view = GiveawayView()
    
    await interaction.response.send_message(f"Starting giveaway for '{prize}'...", ephemeral=True)
    
    # שימוש ב-Embed מעוצב כדי שהטקסט ייראה מרשים ומסודר
    embed = discord.Embed(title="🎉 **GIVEAWAY** 🎉", color=discord.Color.gold())
    embed.add_field(name="Prize", value=prize, inline=False)
    embed.add_field(name="Winners", value=str(winners), inline=True)
    embed.add_field(name="Ends in", value=duration, inline=True)
    embed.add_field(name="Hosted by", value=host.mention, inline=False)

    msg = await interaction.channel.send(embed=embed, view=view)
    
    await asyncio.sleep(duration_seconds)
    
    if len(view.participants) == 0: 
        await msg.reply("Giveaway ended, but nobody entered. 😢")
    else:
        actual_winners_count = min(winners, len(view.participants))
        chosen_winners = random.sample(list(view.participants), actual_winners_count)
        mentions = ", ".join(f"<@{w}>" for w in chosen_winners)
        await msg.reply(f"Congratulations {mentions}! You won **{prize}**! 🎉\n*(Hosted by {host.mention})*")

@giveaway_group.command(name="fast", description="Start an instant click-to-win giveaway")
async def giveaway_fast(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: 
        return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    
    await interaction.response.send_message("Starting Fast Giveaway...", ephemeral=True)
    await interaction.channel.send("⚡ **FAST GIVEAWAY!** First to click the button wins! ⚡", view=FastGiveawayView())

# הוספת קבוצת הפקודות לבוט
bot.tree.add_command(giveaway_group)

# ----------------------------------
TOKEN = os.getenv('TOKEN')
if __name__ == "__main__":
    bot.run(TOKEN)

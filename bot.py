import discord
from discord.ext import commands, tasks
import asyncio
import random
import re
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


# ---------------------------------------------------------
# Channel Settings - Replace with your actual channel IDs!
# ---------------------------------------------------------
WELCOME_CHANNEL_ID = 1541358114538913994  # Welcome channel (Welcomer)
GIVEAWAY_CHANNEL_ID = 1541314936070742068 # Giveaway channel (Giveaway Boat)
NOTIFY_CHANNEL_ID = 1539906472169832559   # Notification channel (NotifyMe)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=['!', 'g.', '?', '/'], intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'✅ Connected as {bot.user.name} ({bot.user.id})')
    channel_notifier.start()
    
# 1. Welcomer
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="👋 New Member Joined!",
            description=f'Welcome to the server, {member.mention}! We are glad to have you here.',
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f'**{member.name}** has left the server. 😢')

# 2. Help Menu
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🛠️ Help Menu", color=discord.Color.blue())
    embed.add_field(name="🎉 Giveaway Boat", value="`!gstart [time like 30m / 8h / 2d] [winners] [prize]` - Create a giveaway (you can attach an image)", inline=False)
    embed.add_field(name="👋 Welcomer", value="Automatic welcome/leave messages", inline=False)
    embed.add_field(name="🔔 NotifyMe", value="Automated background updates", inline=False)
    
    await ctx.author.send(embed=embed)
    await ctx.send(f"{ctx.author.mention}, I have sent you the help menu in your DMs! 📬")

# 3. Giveaway Boat
def parse_time(time_str: str) -> int:
    time_str = time_str.lower()
    match = re.match(r"^(\d+)([mhd]|mo)$", time_str)
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    if unit == "m":
        return amount * 60
    elif unit == "h":
        return amount * 3600
    elif unit == "d":
        return amount * 86400
    elif unit == "mo":
        return amount * 2592000
    return None

class GiveawayView(discord.ui.View):
    def __init__(self, timeout: int, prize: str):
        super().__init__(timeout=timeout)
        self.entrants = set()
        self.prize = prize

    @discord.ui.button(label="Enter (0)", emoji="🎉", style=discord.ButtonStyle.success, custom_id="enter_btn")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.entrants:
            self.entrants.remove(interaction.user)
            button.label = f"Enter ({len(self.entrants)})"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("You have successfully left the giveaway. 🚪", ephemeral=True)
        else:
            self.entrants.add(interaction.user)
            button.label = f"Leave ({len(self.entrants)})"
            button.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("You have successfully entered the giveaway! 🎟️", ephemeral=True)

    @discord.ui.button(label="Check Entrants (Admin)", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="check_btn")
    async def check_entrants(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ This command is restricted to server administrators!", ephemeral=True)
            return
        
        if not self.entrants:
            names = "No participants in the giveaway yet."
        else:
            names = ", ".join(user.mention for user in self.entrants)
            
        try:
            await interaction.user.send(f"📋 **Participants list for the giveaway on {self.prize}:**\n{names}")
            await interaction.response.send_message("Sent you the participants list in DMs! 📭", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Could not send you a DM. Please check your privacy settings.", ephemeral=True)

@bot.command(name='start', aliases=['gstart'])
async def giveaway_start(ctx, time_str: str, winners_count: int, *, prize: str):
    seconds = parse_time(time_str)
    if not seconds:
        await ctx.send("❌ Invalid time format! Use shortcuts like: `30m` (minutes), `8h` (hours), `2d` (days), or `1mo` (month).")
        return

    giveaway_channel = bot.get_channel(GIVEAWAY_CHANNEL_ID)
    if not giveaway_channel:
        await ctx.send("❌ Error: Giveaway channel is not configured correctly in the code.")
        return

    if ctx.channel.id != GIVEAWAY_CHANNEL_ID:
        await ctx.send(f"✅ Giveaway created and sent to {giveaway_channel.mention}!")

    embed = discord.Embed(
        title="🎉 New Giveaway! 🎉", 
        description=f"**Prize:** {prize}\n**Winners:** {winners_count}\n**Duration:** {time_str}\n\nClick the green button below to enter or leave the giveaway!", 
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Giveaway Boat | Created by {ctx.author.name}")
    
    if ctx.message.attachments:
        embed.set_image(url=ctx.message.attachments[0].url)
    
    view = GiveawayView(timeout=seconds, prize=prize)
    msg = await giveaway_channel.send(embed=embed, view=view)
    
    await view.wait()
    
    for child in view.children:
        child.disabled = True
    try:
        await msg.edit(view=view)
    except discord.HTTPException:
        pass
    
    users = list(view.entrants)
    if not users:
        await giveaway_channel.send(f"😥 No one participated in the giveaway for **{prize}**.")
        return

    actual_winners_count = min(winners_count, len(users)) 
    winners = random.sample(users, actual_winners_count)
    winners_mentions = ", ".join(winner.mention for winner in winners)
    
    await giveaway_channel.send(f"🎊 Congratulations to the winners: {winners_mentions}! You won **{prize}**! 🎊\n[Giveaway Link]({msg.jump_url})")
    
    for winner in winners:
        try:
            await winner.send(f"🎉 Congratulations! You won **{prize}** in the giveaway on **{ctx.guild.name}**!\nGiveaway Link: {msg.jump_url}")
        except discord.Forbidden:
            pass
            
    try:
        await ctx.author.send(f"✅ The giveaway you created for **{prize}** has ended!\n**Winners:** {winners_mentions}")
    except discord.Forbidden:
        pass

# 4. NotifyMe
@tasks.loop(minutes=60)
async def channel_notifier():
    notify_channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if notify_channel:
        print("Checking for updates in NotifyMe...")

@channel_notifier.before_loop
async def before_notifier():
    await bot.wait_until_ready()

TOKEN = os.getenv('TOKEN')

if __name__ == "__main__":
    bot.run(TOKEN)

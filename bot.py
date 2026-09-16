import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import os
import re
import feedparser
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

# --- Channel Settings & IDs ---
WELCOME_CHANNEL_ID = 1541358114538913994   
YOUTUBE_CHANNEL_ID = 1539906472169832559   
YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=1539906472169832559"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

last_video_id = None

# --- In-Memory Databases for Items, Coins and XP ---
item_shop_db = {}  
user_coins_db = {} 
user_xp_db = {}    

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
    
    if not youtube_checker_task.is_running():
        youtube_checker_task.start()

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"Welcome to the server, {member.mention}! We are glad to have you here. 🎉")

# --- Background Task: YouTube Checker ---
@tasks.loop(minutes=10)
async def youtube_checker_task():
    global last_video_id
    channel = bot.get_channel(YOUTUBE_CHANNEL_ID)
    if not channel:
        return

    try:
        feed = feedparser.parse(YOUTUBE_RSS_URL)
        if feed.entries:
            latest_video = feed.entries[0]
            video_id = latest_video.id
            video_link = latest_video.link
            video_title = latest_video.title

            if last_video_id is None:
                last_video_id = video_id
            elif last_video_id != video_id:
                last_video_id = video_id
                await channel.send(f"🚨 **New Video Uploaded!** 🚨\n**{video_title}**\n{video_link}")
    except Exception as e:
        print(f"Error checking YouTube RSS: {e}")

@youtube_checker_task.before_loop
async def before_youtube_task():
    await bot.wait_until_ready()

# ==========================================
#         DYNAMIC HELP COMMAND
# ==========================================

@bot.tree.command(name="help", description="Show all available bot commands")
async def help_command(interaction: discord.Interaction):
    help_text = (
        "🤖 **Public Bot Commands:**\n\n"
        "`/ping` - Check if the bot is alive and its latency.\n"
        "`/serverinfo` - Display information about this server.\n"
        "`/xp check` - Check your own XP level.\n"
        "`/coins check` - Check your own balance.\n"
    )

    if interaction.user.guild_permissions.administrator:
        help_text += (
            "\n🛡️ **SERVER TEAM (Admin Commands):**\n\n"
            "`/giveaway` - Start a giveaway (timed or fast mode).\n"
            "`/clear [amount]` - Delete multiple messages.\n"
            "`/modpanel` - Open admin control panel.\n"
            "`/itemshop add/remove/view` - Item Shop management.\n"
            "`/coins add/remove/check [user]` - Manage or check anyone's coins.\n"
            "`/xp add/remove/check [user]` - Manage or check anyone's XP."
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
#         ADMIN COMMANDS & SYSTEMS
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

# --- Item Shop Group (Admin Only) ---
itemshop_group = app_commands.Group(name="itemshop", description="Manage item shop (Admin only)")

@itemshop_group.command(name="add", description="Add an item to the shop")
@app_commands.describe(item_name="Name of the item", price="Price of the item")
async def itemshop_add(interaction: discord.Interaction, item_name: str, price: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    item_shop_db[item_name] = price
    await interaction.response.send_message(f"🛒 Successfully added **{item_name}** to the shop for **{price}** coins!", ephemeral=True)

@itemshop_group.command(name="remove", description="Remove an item from the shop")
@app_commands.describe(item_name="Name of the item to remove")
async def itemshop_remove(interaction: discord.Interaction, item_name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    if item_name in item_shop_db:
        del item_shop_db[item_name]
        await interaction.response.send_message(f"🗑️ Successfully removed **{item_name}** from the shop.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Item **{item_name}** not found in the shop.", ephemeral=True)

@itemshop_group.command(name="view", description="View all items in the shop")
async def itemshop_view(interaction: discord.Interaction):
    if not item_shop_db:
        await interaction.response.send_message("🛒 The item shop is currently empty.")
    else:
        shop_list = "\n".join([f"• **{item}** - {price} coins" for item, price in item_shop_db.items()])
        await interaction.response.send_message(f"🛒 **Server Item Shop:**\n\n{shop_list}")

bot.tree.add_command(itemshop_group)

# --- Coins System Group ---
coins_group = app_commands.Group(name="coins", description="Manage or check coins")

@coins_group.command(name="add", description="Add coins to a user (Admin only)")
@app_commands.describe(user="The user to give coins to", amount="Amount of coins")
async def coins_add(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    user_coins_db[user.id] = user_coins_db.get(user.id, 0) + amount
    await interaction.response.send_message(f"🪙 Successfully added **{amount} coins** to {user.mention}. Total: **{user_coins_db[user.id]}** coins", ephemeral=True)

@coins_group.command(name="remove", description="Remove coins from a user (Admin only)")
@app_commands.describe(user="The user to take coins from", amount="Amount of coins")
async def coins_remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    current_coins = user_coins_db.get(user.id, 0)
    new_coins = max(0, current_coins - amount)
    user_coins_db[user.id] = new_coins
    await interaction.response.send_message(f"🪙 Successfully removed **{amount} coins** from {user.mention}. Total: **{new_coins}** coins", ephemeral=True)

@coins_group.command(name="check", description="Check user coins balance")
@app_commands.describe(user="The user to check (Admin only to check others, everyone for self)")
async def coins_check(interaction: discord.Interaction, user: discord.Member = None):
    if user is not None and user.id != interaction.user.id:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 **Access Denied:** Only admins can check other users' balance.", ephemeral=True)
            return
        target = user
    else:
        target = interaction.user
    
    coins = user_coins_db.get(target.id, 0)
    await interaction.response.send_message(f"🪙 **{target.display_name}'s Balance:** {coins} coins")

bot.tree.add_command(coins_group)

# --- XP System Group ---
xp_group = app_commands.Group(name="xp", description="Manage or check user XP")

@xp_group.command(name="add", description="Add XP to a user (Admin only)")
@app_commands.describe(user="The user to give XP to", amount="Amount of XP")
async def xp_add(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    user_xp_db[user.id] = user_xp_db.get(user.id, 0) + amount
    await interaction.response.send_message(f"⭐ Successfully added **{amount} XP** to {user.mention}. Total XP: **{user_xp_db[user.id]}**", ephemeral=True)

@xp_group.command(name="remove", description="Remove XP from a user (Admin only)")
@app_commands.describe(user="The user to take XP from", amount="Amount of XP")
async def xp_remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return
    current_xp = user_xp_db.get(user.id, 0)
    new_xp = max(0, current_xp - amount)
    user_xp_db[user.id] = new_xp
    await interaction.response.send_message(f"⭐ Successfully removed **{amount} XP** from {user.mention}. Total XP: **{new_xp}**", ephemeral=True)

@xp_group.command(name="check", description="Check user XP")
@app_commands.describe(user="The user to check (Admin only to check others, everyone for self)")
async def xp_check(interaction: discord.Interaction, user: discord.Member = None):
    if user is not None and user.id != interaction.user.id:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 **Access Denied:** Only admins can check other users' XP.", ephemeral=True)
            return
        target = user
    else:
        target = interaction.user
    
    xp = user_xp_db.get(target.id, 0)
    await interaction.response.send_message(f"⭐ **{target.display_name}'s XP:** {xp} XP")

bot.tree.add_command(xp_group)

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
#             SMART GIVEAWAY SYSTEM
# ==========================================

class AdminManageView(discord.ui.Select):
    def __init__(self, giveaway_view):
        self.giveaway_view = giveaway_view
        options = []
        
        if not giveaway_view.participants:
            options.append(discord.SelectOption(label="No participants yet", value="none"))
        else:
            for uid in giveaway_view.participants:
                options.append(discord.SelectOption(label=f"User ID: {uid}", value=str(uid)))

        super().__init__(placeholder="Select a participant to remove...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return

        if self.values[0] == "none":
            await interaction.response.send_message("No participants to remove.", ephemeral=True)
            return

        user_id_to_remove = int(self.values[0])
        if user_id_to_remove in self.giveaway_view.participants:
            self.giveaway_view.participants.remove(user_id_to_remove)
            self.giveaway_view.update_button_label()
            try:
                await self.giveaway_view.message_ref.edit(view=self.giveaway_view)
            except Exception:
                pass
            await interaction.response.send_message(f"Successfully removed user <@{user_id_to_remove}> from the giveaway.", ephemeral=True)
        else:
            await interaction.response.send_message("User is no longer in the giveaway.", ephemeral=True)

class AdminManageModalView(discord.ui.View):
    def __init__(self, giveaway_view):
        super().__init__(timeout=None)
        self.add_item(AdminManageView(giveaway_view))

class SmartGiveawayView(discord.ui.View):
    def __init__(self, is_fast_mode: bool, max_winners: int, message_ref=None):
        super().__init__(timeout=None)
        self.participants = [] 
        self.is_fast_mode = is_fast_mode
        self.max_winners = max_winners
        self.ended = False
        self.message_ref = message_ref

    def update_button_label(self):
        for child in self.children:
            if child.custom_id == "gw_enter":
                if self.is_fast_mode:
                    child.label = f"Enter Giveaway 🎉"
                else:
                    child.label = f"Enter Giveaway 🎉 ({len(self.participants)})"
                
                if self.ended:
                    child.disabled = True
                break

    @discord.ui.button(label="Enter Giveaway 🎉 (0)", style=discord.ButtonStyle.green, custom_id="gw_enter")
    async def enter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ended:
            await interaction.response.send_message("This giveaway has already ended!", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in self.participants:
            msg = "You already claimed your spot!" if self.is_fast_mode else "You are already in the giveaway!"
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            self.participants.append(user_id)
            self.update_button_label()

            if self.is_fast_mode and len(self.participants) >= self.max_winners:
                self.ended = True
                for child in self.children:
                    child.disabled = True

            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                pass

            if self.is_fast_mode and self.ended and self.message_ref:
                mentions = ", ".join(f"<@{w}>" for w in self.participants)
                await self.message_ref.reply(f"⚡ **Fastest fingers first!** Winner: {mentions} won **the prize**! 🎉")
                await interaction.followup.send("You secured your spot and won!", ephemeral=True)
            else:
                success_msg = "You claimed a spot successfully!" if self.is_fast_mode else "You entered the giveaway successfully!"
                await interaction.followup.send(success_msg, ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="gw_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ended:
            await interaction.response.send_message("This giveaway has already ended!", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in self.participants:
            self.participants.remove(user_id)
            self.update_button_label()
            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                pass
            await interaction.followup.send("You left the giveaway.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not in the giveaway.", ephemeral=True)

    @discord.ui.button(label="Manage Participants 🛡️", style=discord.ButtonStyle.grey, custom_id="gw_manage")
    async def manage_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
            return
        
        if not self.participants:
            await interaction.response.send_message("There are no participants in this giveaway yet.", ephemeral=True)
            return

        view = AdminManageModalView(self)
        await interaction.response.send_message("Select a participant from the dropdown below to remove them:", view=view, ephemeral=True)

@bot.tree.command(name="giveaway", description="Start a giveaway (Admin only)")
@app_commands.describe(
    prize="What is the prize?", 
    duration="Leave empty or type 'fast' for instant fastest-fingers mode (otherwise enter time like 10M, 2H)",
    winners="Number of winners (leave empty for fast mode default: 1)"
)
async def start_giveaway(interaction: discord.Interaction, prize: str, duration: str = "fast", winners: int = 1):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 **Access Denied:** Admins only.", ephemeral=True)
        return

    is_fast_mode = duration is None or duration.strip().lower() == "fast"

    if not is_fast_mode:
        try:
            duration_seconds = parse_duration(duration)
        except Exception:
            await interaction.response.send_message("Invalid duration format! Use M, H, D, MO or leave empty / type 'fast'.", ephemeral=True)
            return

    view = SmartGiveawayView(is_fast_mode=is_fast_mode, max_winners=winners)
    await interaction.response.send_message(f"Starting giveaway for '{prize}'...", ephemeral=True)

    if is_fast_mode:
        view.update_button_label()
        msg = await interaction.channel.send(
            f"⚡ **FASTEST FINGERS GIVEAWAY** ⚡\n**Prize:** {prize}\n*First person to click the button wins instantly!*", 
            view=view
        )
    else:
        msg = await interaction.channel.send(
            f"🎉 **GIVEAWAY** 🎉\n**Prize:** {prize}\n**Winners:** {winners}\nEnds in **{duration}**!", 
            view=view
        )
    
    view.message_ref = msg

    if not is_fast_mode:
        elapsed = 0
        while elapsed < duration_seconds and not view.ended:
            await asyncio.sleep(1)
            elapsed += 1

        if not view.ended:
            view.ended = True
            for child in view.children:
                if child.custom_id != "gw_manage": # keep manage active or disable all
                    child.disabled = True
            try:
                await msg.edit(view=view)
            except Exception:
                pass

            if len(view.participants) == 0:
                await msg.reply("Giveaway ended, but nobody entered. 😢")
            else:
                actual_winners_count = min(winners, len(view.participants))
                chosen_winners = random.sample(view.participants, actual_winners_count)
                mentions = ", ".join(f"<@{w}>" for w in chosen_winners)
                await msg.reply(f"Congratulations {mentions}! You won **{prize}**! 🎉")

# ----------------------------------
# Secure Token Execution
TOKEN = os.getenv('TOKEN')

if __name__ == "__main__":
    bot.run(TOKEN)

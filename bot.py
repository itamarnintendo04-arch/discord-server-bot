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
WELCOME_CHANNEL_ID = 1541358114538913994   
YOUTUBE_CHANNEL_ID = 1539906472169832559   

# --- Databases ---
global_coins = {}         # {user_id: coin_amount}
store_coins = {}          # {store_name: {user_id: coin_amount}}
admin_shop_items = {      # Default Admin Shop
    "VIP Role": 100,
    "Custom Color": 50
}
player_shops = {}         # {store_name: {"owner_id": int, "managers": set(), "category": str, "items": {item_name: price}}}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- Helper Functions ---
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

def is_store_manager(user: discord.Member, store_name: str) -> bool:
    if user.guild_permissions.administrator:
        return True
    if store_name in player_shops:
        store = player_shops[store_name]
        return user.id == store["owner_id"] or user.id in store["managers"]
    return False

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
    help_text = (
        "🤖 **Public Commands:**\n"
        "`/ping`, `/serverinfo`, `/balance`\n"
        "`/shop` - Main Server Shop\n"
        "`/donate [user] [amount]` - Donate global coins\n\n"
        "🛍️ **Player Shop Commands:**\n"
        "`/create-mystore [store_name] [category]` - Create a store\n"
        "`/add-mystore-item [store_name] [item] [price]` - Add item to store\n"
        "`/add-store-manager [store_name] [user]` - Add store co-owner\n"
        "`/add-store-coins [store_name] [user] [amount]` - Add store-specific coins\n"
        "`/mystore [store_name]` - Open a player store\n"
    )

    if interaction.user.guild_permissions.administrator:
        help_text += (
            "\n🛡️ **SERVER TEAM (Admin Only):**\n"
            "`/giveaway [mode] [prize] [duration] [winners]` - Start giveaway\n"
            "`/clear [amount]`, `/modpanel`\n"
            "`/addcoins [user] [amount]` - Add global coins for all shops\n"
            "`/add-shop-item [name] [price]` - Add item to Main Shop\n"
        )

    await interaction.response.send_message(help_text, ephemeral=True)


# ==========================================
#         ECONOMY & DONATE COMMANDS
# ==========================================

@bot.tree.command(name="ping", description="Check bot latency")
async def ping_command(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is {latency}ms.", ephemeral=True)

@bot.tree.command(name="serverinfo", description="Get server info")
async def serverinfo_command(interaction: discord.Interaction):
    guild = interaction.guild
    info = f"**Server Name:** {guild.name}\n**Members:** {guild.member_count}"
    await interaction.response.send_message(info, ephemeral=True)

@bot.tree.command(name="balance", description="Check your global and store coins")
async def balance_command(interaction: discord.Interaction):
    uid = interaction.user.id
    g_coins = global_coins.get(uid, 0)
    
    msg = f"💰 **Global Coins:** {g_coins}\n"
    s_balances = []
    for s_name, users in store_coins.items():
        if uid in users and users[uid] > 0:
            s_balances.append(f"🔹 **{s_name}:** {users[uid]} store coins")
    
    if s_balances:
        msg += "\n🏪 **Store-Specific Coins:**\n" + "\n".join(s_balances)

    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="donate", description="Donate global coins to another member")
@app_commands.describe(member="Member to donate to", amount="Amount of coins")
async def donate_command(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be > 0.", ephemeral=True)
        return

    sender_id = interaction.user.id
    sender_coins = global_coins.get(sender_id, 0)

    if sender_coins < amount:
        await interaction.response.send_message(f"❌ You need {amount} coins, but only have {sender_coins}.", ephemeral=True)
        return

    global_coins[sender_id] = sender_coins - amount
    global_coins[member.id] = global_coins.get(member.id, 0) + amount

    await interaction.response.send_message(f"🎁 Donated **{amount}** global coins to {member.mention}!", ephemeral=True)


# ==========================================
#         MAIN SERVER SHOP
# ==========================================

class AdminShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for item_name, price in admin_shop_items.items():
            self.add_item(AdminShopButton(item_name, price))

class AdminShopButton(discord.ui.Button):
    def __init__(self, item_name: str, price: int):
        super().__init__(label=f"Buy {item_name} ({price} Coins)", style=discord.ButtonStyle.green)
        self.item_name = item_name
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        uid = interaction.user.id
        current = global_coins.get(uid, 0)

        if current >= self.price:
            global_coins[uid] = current - self.price
            await interaction.response.send_message(f"🎉 Bought **{self.item_name}**! Remaining: {global_coins[uid]} coins.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ You need {self.price} global coins. You have {current}.", ephemeral=True)

@bot.tree.command(name="shop", description="Open the main server shop")
async def shop_command(interaction: discord.Interaction):
    if not admin_shop_items:
        await interaction.response.send_message("🛒 Main shop is empty.", ephemeral=True)
        return

    shop_text = "🛒 **Main Server Shop** (Uses Global Coins):\n"
    for item, price in admin_shop_items.items():
        shop_text += f"🔹 **{item}** - {price} Coins\n"

    view = AdminShopView()
    await interaction.response.send_message(shop_text, view=view)


# ==========================================
#         ADVANCED PLAYER SHOPS
# ==========================================

@bot.tree.command(name="create-mystore", description="Create a new shop in a specific category")
@app_commands.describe(store_name="Unique Store Name", category="Category (e.g. Roles, Games, Colors)")
async def create_mystore(interaction: discord.Interaction, store_name: str, category: str):
    if store_name in player_shops:
        await interaction.response.send_message("❌ A store with this name already exists!", ephemeral=True)
        return

    player_shops[store_name] = {
        "owner_id": interaction.user.id,
        "managers": set(),
        "category": category,
        "items": {}
    }
    
    # הודעה חגיגית וגלויה לכולם בערוץ!
    public_msg = (
        f"🏪 **New Store Opened!** 🎉\n"
        f"👤 **Owner:** {interaction.user.mention}\n"
        f"🏷️ **Store Name:** **{store_name}**\n"
        f"📁 **Category:** {category}\n\n"
        f"*(Use `/mystore {store_name}` to check it out!)*"
    )
    await interaction.response.send_message(public_msg)

@bot.tree.command(name="add-store-manager", description="Add a co-owner/manager to your store")
@app_commands.describe(store_name="Your store name", member="Member to add as manager")
async def add_store_manager(interaction: discord.Interaction, store_name: str, member: discord.Member):
    if not is_store_manager(interaction.user, store_name):
        await interaction.response.send_message("🚫 Only the store owner or server admins can add managers.", ephemeral=True)
        return

    player_shops[store_name]["managers"].add(member.id)
    await interaction.response.send_message(f"✅ Added {member.mention} as a manager for **{store_name}**!", ephemeral=True)

@bot.tree.command(name="add-mystore-item", description="Add item to your store")
@app_commands.describe(store_name="Store name", item_name="Item name", price="Price")
async def add_mystore_item(interaction: discord.Interaction, store_name: str, item_name: str, price: int):
    if not is_store_manager(interaction.user, store_name):
        await interaction.response.send_message("🚫 You do not have permission to manage this store.", ephemeral=True)
        return

    player_shops[store_name]["items"][item_name] = price
    await interaction.response.send_message(f"✅ Added **{item_name}** ({price} coins) to **{store_name}**!", ephemeral=True)

@bot.tree.command(name="add-store-coins", description="Give coins valid ONLY in your store")
@app_commands.describe(store_name="Store name", member="Target member", amount="Coins amount")
async def add_store_coins(interaction: discord.Interaction, store_name: str, member: discord.Member, amount: int):
    if not is_store_manager(interaction.user, store_name):
        await interaction.response.send_message("🚫 Only store managers/admins can add store coins.", ephemeral=True)
        return

    if store_name not in store_coins:
        store_coins[store_name] = {}

    current = store_coins[store_name].get(member.id, 0)
    store_coins[store_name][member.id] = current + amount
    await interaction.response.send_message(f"✅ Added {amount} **{store_name}** coins to {member.mention}!", ephemeral=True)

class PlayerShopView(discord.ui.View):
    def __init__(self, store_name: str):
        super().__init__(timeout=None)
        items = player_shops[store_name]["items"]
        for item_name, price in items.items():
            self.add_item(PlayerShopButton(store_name, item_name, price))

class PlayerShopButton(discord.ui.Button):
    def __init__(self, store_name: str, item_name: str, price: int):
        super().__init__(label=f"Buy {item_name} ({price}c)", style=discord.ButtonStyle.blurple)
        self.store_name = store_name
        self.item_name = item_name
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        buyer_id = interaction.user.id
        
        # Check coins (Store coins first, then Global coins)
        s_coins = store_coins.get(self.store_name, {}).get(buyer_id, 0)
        g_coins = global_coins.get(buyer_id, 0)

        if s_coins >= self.price:
            store_coins[self.store_name][buyer_id] -= self.price
            pay_method = f"used {self.store_name} coins"
        elif g_coins >= self.price:
            global_coins[buyer_id] -= self.price
            # Pay global coins to store owner
            owner_id = player_shops[self.store_name]["owner_id"]
            global_coins[owner_id] = global_coins.get(owner_id, 0) + self.price
            pay_method = "used Global coins"
        else:
            await interaction.response.send_message(f"❌ Not enough coins! You need {self.price} coins.", ephemeral=True)
            return

        await interaction.response.send_message(f"🎉 Success! Bought **{self.item_name}** ({pay_method}).", ephemeral=True)

@bot.tree.command(name="mystore", description="View a player store")
@app_commands.describe(store_name="Store name")
async def mystore_command(interaction: discord.Interaction, store_name: str):
    if store_name not in player_shops:
        await interaction.response.send_message("❌ Store not found.", ephemeral=True)
        return

    store = player_shops[store_name]
    text = f"🛍️ **Store: {store_name}** (Category: {store['category']})\n"
    for item, price in store["items"].items():
        text += f"🔹 **{item}** - {price} Coins\n"

    view = PlayerShopView(store_name)
    await interaction.response.send_message(text, view=view)


# ==========================================
#         ADMIN COMMANDS
# ==========================================

@bot.tree.command(name="addcoins", description="Add Global Coins for ALL shops (Admin only)")
@app_commands.describe(member="Member", amount="Amount")
async def addcoins_command(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
        return

    global_coins[member.id] = global_coins.get(member.id, 0) + amount
    await interaction.response.send_message(f"✅ Added {amount} Global Coins to {member.mention}.", ephemeral=True)

@bot.tree.command(name="add-shop-item", description="Add item to Main Server Shop (Admin only)")
@app_commands.describe(name="Item name", price="Price")
async def add_shop_item(interaction: discord.Interaction, name: str, price: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
        return
    admin_shop_items[name] = price
    await interaction.response.send_message(f"✅ Added **{name}** to Main Shop!", ephemeral=True)

@bot.tree.command(name="clear", description="Clear messages (Admin only)")
@app_commands.describe(amount="Amount")
async def clear_command(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clear 5 Messages 🧹", style=discord.ButtonStyle.red, custom_id="admin_clear_5")
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=5)
        await interaction.followup.send("Deleted 5 messages.", ephemeral=True)

@bot.tree.command(name="modpanel", description="Admin control panel (Admin only)")
async def modpanel_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
        return
    await interaction.response.send_message("🛠️ **Admin Panel**", view=AdminPanelView(), ephemeral=True)


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

    @discord.ui.button(label="⚡ CLAIM FAST! ⚡", style=discord.ButtonStyle.blurple, custom_id="gw_fast")
    async def fast_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed:
            await interaction.response.send_message("Too late! Someone already claimed it.", ephemeral=True)
            return

        self.claimed = True
        button.disabled = True
        button.label = "CLAIMED!"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"⚡ 🎉 {interaction.user.mention} won the **Fast Giveaway**! 🎉 ⚡")

@bot.tree.command(name="giveaway", description="Start a giveaway (Admin only)")
@app_commands.describe(
    mode="random (Normal) or fast (Instant click)",
    prize="Prize name (Optional for fast)",
    duration="Duration (e.g. 5M, 2H) - (Ignored for fast)",
    winners="Number of winners - (Ignored for fast)"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="Random (Normal Giveaway)", value="random"),
    app_commands.Choice(name="Fast (First to click wins)", value="fast")
])
async def start_giveaway(
    interaction: discord.Interaction, 
    mode: app_commands.Choice[str], 
    prize: str = "Fast Prize", 
    duration: str = "1M", 
    winners: int = 1
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
        return

    # 1. FAST MODE
    if mode.value == "fast":
        await interaction.response.send_message("Starting Fast Giveaway...", ephemeral=True)
        view = FastGiveawayView()
        await interaction.channel.send("⚡ **FAST GIVEAWAY!** First to click the button wins! ⚡", view=view)
        return

    # 2. RANDOM (NORMAL) MODE
    try:
        duration_seconds = parse_duration(duration)
    except Exception:
        await interaction.response.send_message("Invalid duration format! Use M, H, D, or MO.", ephemeral=True)
        return

    view = GiveawayView()
    await interaction.response.send_message(f"Starting giveaway for '{prize}'...", ephemeral=True)
    
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
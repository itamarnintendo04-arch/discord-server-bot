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
global_coins = {}         
store_coins = {}          
# admin_shop_items: { "Item Name": {"price": int, "stock": int, "link": str} }
admin_shop_items = {      
    "VIP Role": {"price": 100, "stock": 999, "link": "Auto-assigned by Admin"},
    "Custom Color": {"price": 50, "stock": 999, "link": "Contact Admin for color"}
}
# player_shops: { "Store Name": {"owner_id": int, "managers": set(), "category": str, "items": {"Item": {"price": int, "stock": int, "link": str}}} }
player_shops = {}         

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- Helper Functions ---
def parse_duration(duration_str: str) -> int:
    duration_str = duration_str.upper()
    if duration_str.endswith('MO'): return int(duration_str[:-2]) * 30 * 24 * 60 * 60
    elif duration_str.endswith('M'): return int(duration_str[:-1]) * 60
    elif duration_str.endswith('H'): return int(duration_str[:-1]) * 60 * 60
    elif duration_str.endswith('D'): return int(duration_str[:-1]) * 24 * 60 * 60
    else: return int(duration_str)

def is_store_manager(user: discord.Member, store_name: str) -> bool:
    if user.guild_permissions.administrator: return True
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
    if channel: pass 

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
        "`/add-mystore-item [store] [item] [price] [stock] [link]` - Add item\n"
        "`/update-mystore-item [store] [item] [stock] [link]` - Update stock/link\n"
        "`/add-store-manager [store] [user]` - Add store co-owner\n"
        "`/add-store-coins [store] [user] [amount]` - Add store coins\n"
        "`/mystore [store_name]` - Open a player store\n"
    )

    if interaction.user.guild_permissions.administrator:
        help_text += (
            "\n🛡️ **SERVER TEAM (Admin Only):**\n"
            "`/giveaway [mode] [prize] [time] [winners]`\n"
            "`/clear [amount]`, `/modpanel`\n"
            "`/addcoins [user] [amount]`\n"
            "`/add-shop-item [name] [price] [stock] [link]`\n"
            "`/update-shop-item [name] [stock] [link]`\n"
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
    
    if s_balances: msg += "\n🏪 **Store-Specific Coins:**\n" + "\n".join(s_balances)
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="donate", description="Donate global coins to another member")
@app_commands.describe(member="Member to donate to", amount="Amount of coins")
async def donate_command(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0: return await interaction.response.send_message("❌ Amount must be > 0.", ephemeral=True)
    sender_id = interaction.user.id
    sender_coins = global_coins.get(sender_id, 0)

    if sender_coins < amount: return await interaction.response.send_message(f"❌ Not enough coins! You have {sender_coins}.", ephemeral=True)
    if member.id == sender_id: return await interaction.response.send_message("❌ You cannot donate to yourself!", ephemeral=True)

    global_coins[sender_id] = sender_coins - amount
    global_coins[member.id] = global_coins.get(member.id, 0) + amount
    await interaction.response.send_message(f"🎁 Donated **{amount}** global coins to {member.mention}!", ephemeral=True)


# ==========================================
#         MAIN SERVER SHOP
# ==========================================

class AdminShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for item_name, data in admin_shop_items.items():
            self.add_item(AdminShopButton(item_name, data["price"], data["stock"]))

class AdminShopButton(discord.ui.Button):
    def __init__(self, item_name: str, price: int, stock: int):
        super().__init__(label=f"Buy {item_name} ({price}c) [Stock: {stock}]", style=discord.ButtonStyle.green)
        self.item_name = item_name
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        uid = interaction.user.id
        current = global_coins.get(uid, 0)
        item_data = admin_shop_items[self.item_name]

        if item_data["stock"] <= 0:
            return await interaction.response.send_message(f"❌ **{self.item_name}** is out of stock!", ephemeral=True)

        if current >= self.price:
            global_coins[uid] = current - self.price
            item_data["stock"] -= 1 # Reduce stock
            
            # Green Embed Message
            embed = discord.Embed(title="🎉 Purchase Successful!", description=f"You bought **{self.item_name}**!\nRemaining balance: {global_coins[uid]} coins.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

            # DM Buyer
            try:
                await interaction.user.send(f"🎉 Thank you for purchasing **{self.item_name}**!\n🔗 **Here is your link/info:** {item_data['link']}")
            except: pass

            # DM Admins
            for member in interaction.guild.members:
                if member.guild_permissions.administrator and not member.bot:
                    try:
                        await member.send(f"🛒 **Main Shop Alert:** {interaction.user.name} bought **{self.item_name}**.\n*(They received this link: {item_data['link']})*")
                    except: pass
        else:
            await interaction.response.send_message(f"❌ You need {self.price} global coins. You have {current}.", ephemeral=True)

@bot.tree.command(name="shop", description="Open the main server shop")
async def shop_command(interaction: discord.Interaction):
    if not admin_shop_items: return await interaction.response.send_message("🛒 Main shop is empty.", ephemeral=True)

    shop_text = "🛒 **Main Server Shop** (Uses Global Coins):\n"
    for item, data in admin_shop_items.items():
        shop_text += f"🔹 **{item}** - {data['price']} Coins (Stock: {data['stock']})\n"

    view = AdminShopView()
    await interaction.response.send_message(shop_text, view=view)


# ==========================================
#         ADVANCED PLAYER SHOPS
# ==========================================

@bot.tree.command(name="create-mystore", description="Create a new shop in a specific category")
@app_commands.describe(store_name="Unique Store Name", category="Category (e.g. Roles, Games, Colors)")
async def create_mystore(interaction: discord.Interaction, store_name: str, category: str):
    if store_name in player_shops: return await interaction.response.send_message("❌ A store with this name already exists!", ephemeral=True)

    player_shops[store_name] = {"owner_id": interaction.user.id, "managers": set(), "category": category, "items": {}}
    
    public_msg = (
        f"🏪 **New Store Opened!** 🎉\n👤 **Owner:** {interaction.user.mention}\n"
        f"🏷️ **Store Name:** **{store_name}**\n📁 **Category:** {category}\n\n"
        f"*(Use `/mystore {store_name}` to check it out!)*"
    )
    await interaction.response.send_message(public_msg)

@bot.tree.command(name="add-store-manager", description="Add a co-owner/manager to your store")
async def add_store_manager(interaction: discord.Interaction, store_name: str, member: discord.Member):
    if not is_store_manager(interaction.user, store_name): return await interaction.response.send_message("🚫 Only the store owner or admins can do this.", ephemeral=True)
    player_shops[store_name]["managers"].add(member.id)
    await interaction.response.send_message(f"✅ Added {member.mention} as a manager for **{store_name}**!", ephemeral=True)

@bot.tree.command(name="add-mystore-item", description="Add item to your store")
@app_commands.describe(store_name="Store name", item_name="Item name", price="Price", stock="Available stock", link="The link/info given to the buyer")
async def add_mystore_item(interaction: discord.Interaction, store_name: str, item_name: str, price: int, stock: int, link: str):
    if not is_store_manager(interaction.user, store_name): return await interaction.response.send_message("🚫 You do not have permission.", ephemeral=True)
    player_shops[store_name]["items"][item_name] = {"price": price, "stock": stock, "link": link}
    await interaction.response.send_message(f"✅ Added **{item_name}** (Price: {price}, Stock: {stock}) to **{store_name}**!", ephemeral=True)

@bot.tree.command(name="update-mystore-item", description="Update an item's stock or link in your store")
@app_commands.describe(store_name="Store name", item_name="Item name", new_stock="New stock amount (Optional)", new_link="New link (Optional)")
async def update_mystore_item(interaction: discord.Interaction, store_name: str, item_name: str, new_stock: int = None, new_link: str = None):
    if not is_store_manager(interaction.user, store_name): return await interaction.response.send_message("🚫 You do not have permission.", ephemeral=True)
    if item_name not in player_shops[store_name]["items"]: return await interaction.response.send_message("❌ Item not found.", ephemeral=True)
    
    item = player_shops[store_name]["items"][item_name]
    if new_stock is not None: item["stock"] = new_stock
    if new_link is not None: item["link"] = new_link
    await interaction.response.send_message(f"✅ Updated **{item_name}**! New Stock: {item['stock']}, Link: {item['link']}", ephemeral=True)

@bot.tree.command(name="add-store-coins", description="Give coins valid ONLY in your store")
async def add_store_coins(interaction: discord.Interaction, store_name: str, member: discord.Member, amount: int):
    if not is_store_manager(interaction.user, store_name): return await interaction.response.send_message("🚫 Only store managers/admins can add store coins.", ephemeral=True)
    if store_name not in store_coins: store_coins[store_name] = {}
    store_coins[store_name][member.id] = store_coins[store_name].get(member.id, 0) + amount
    await interaction.response.send_message(f"✅ Added {amount} **{store_name}** coins to {member.mention}!", ephemeral=True)

class PlayerShopView(discord.ui.View):
    def __init__(self, store_name: str):
        super().__init__(timeout=None)
        items = player_shops[store_name]["items"]
        for item_name, data in items.items():
            self.add_item(PlayerShopButton(store_name, item_name, data["price"], data["stock"]))

class PlayerShopButton(discord.ui.Button):
    def __init__(self, store_name: str, item_name: str, price: int, stock: int):
        super().__init__(label=f"Buy {item_name} ({price}c) [Stock: {stock}]", style=discord.ButtonStyle.blurple)
        self.store_name = store_name
        self.item_name = item_name
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        buyer_id = interaction.user.id
        item_data = player_shops[self.store_name]["items"][self.item_name]
        
        if item_data["stock"] <= 0:
            return await interaction.response.send_message("❌ Out of stock!", ephemeral=True)

        s_coins = store_coins.get(self.store_name, {}).get(buyer_id, 0)
        g_coins = global_coins.get(buyer_id, 0)

        if s_coins >= self.price:
            store_coins[self.store_name][buyer_id] -= self.price
            pay_method = f"used {self.store_name} coins"
        elif g_coins >= self.price:
            global_coins[buyer_id] -= self.price
            owner_id = player_shops[self.store_name]["owner_id"]
            global_coins[owner_id] = global_coins.get(owner_id, 0) + self.price
            pay_method = "used Global coins"
        else:
            return await interaction.response.send_message(f"❌ Not enough coins! You need {self.price} coins.", ephemeral=True)

        item_data["stock"] -= 1 # Reduce stock
        
        # Green Embed Message
        embed = discord.Embed(title="🎉 Purchase Successful!", description=f"You bought **{self.item_name}** from **{self.store_name}** ({pay_method}).", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # DM Buyer
        try: await interaction.user.send(f"🎉 Thank you for buying **{self.item_name}** from **{self.store_name}**!\n🔗 **Link:** {item_data['link']}")
        except: pass

        # DM Store Owner & Admins
        owner_id = player_shops[self.store_name]["owner_id"]
        owner = interaction.guild.get_member(owner_id)
        if owner:
            try: await owner.send(f"🛍️ **Store Alert:** {interaction.user.name} bought **{self.item_name}** from your store ({self.store_name}). If they have issues with the link, please help them!")
            except: pass

@bot.tree.command(name="mystore", description="View a player store")
async def mystore_command(interaction: discord.Interaction, store_name: str):
    if store_name not in player_shops: return await interaction.response.send_message("❌ Store not found.", ephemeral=True)
    store = player_shops[store_name]
    text = f"🛍️ **Store: {store_name}** (Category: {store['category']})\n"
    for item, data in store["items"].items(): text += f"🔹 **{item}** - {data['price']} Coins (Stock: {data['stock']})\n"
    await interaction.response.send_message(text, view=PlayerShopView(store_name))


# ==========================================
#         ADMIN COMMANDS
# ==========================================

@bot.tree.command(name="addcoins", description="Add Global Coins for ALL shops (Admin only)")
async def addcoins_command(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    global_coins[member.id] = global_coins.get(member.id, 0) + amount
    await interaction.response.send_message(f"✅ Added {amount} Global Coins to {member.mention}.", ephemeral=True)

@bot.tree.command(name="add-shop-item", description="Add item to Main Server Shop (Admin only)")
@app_commands.describe(name="Item name", price="Price", stock="Stock amount", link="Link given to buyer")
async def add_shop_item(interaction: discord.Interaction, name: str, price: int, stock: int, link: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    admin_shop_items[name] = {"price": price, "stock": stock, "link": link}
    await interaction.response.send_message(f"✅ Added **{name}** to Main Shop!", ephemeral=True)

@bot.tree.command(name="update-shop-item", description="Update an item in the Main Shop (Admin only)")
@app_commands.describe(name="Item name", new_stock="New stock (Optional)", new_link="New link (Optional)")
async def update_shop_item(interaction: discord.Interaction, name: str, new_stock: int = None, new_link: str = None):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    if name not in admin_shop_items: return await interaction.response.send_message("❌ Item not found.", ephemeral=True)
    
    item = admin_shop_items[name]
    if new_stock is not None: item["stock"] = new_stock
    if new_link is not None: item["link"] = new_link
    await interaction.response.send_message(f"✅ Updated **{name}**! New Stock: {item['stock']}", ephemeral=True)

@bot.tree.command(name="clear", description="Clear messages (Admin only)")
async def clear_command(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clear 5 Messages 🧹", style=discord.ButtonStyle.red, custom_id="admin_clear_5")
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=5)
        await interaction.followup.send("Deleted 5 messages.", ephemeral=True)

@bot.tree.command(name="modpanel", description="Admin control panel (Admin only)")
async def modpanel_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
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
        if self.claimed: return await interaction.response.send_message("Too late! Someone already claimed it.", ephemeral=True)
        self.claimed = True
        button.disabled = True
        button.label = "CLAIMED!"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"⚡ 🎉 {interaction.user.mention} won the **Fast Giveaway**! 🎉 ⚡")

@bot.tree.command(name="giveaway", description="Start a giveaway (Admin only)")
@app_commands.describe(mode="random or fast", prize="Prize name", duration="Duration (e.g. 5M, 2H)", winners="Number of winners")
@app_commands.choices(mode=[
    app_commands.Choice(name="Random (Normal Giveaway)", value="random"),
    app_commands.Choice(name="Fast (First to click wins)", value="fast")
])
async def start_giveaway(interaction: discord.Interaction, mode: app_commands.Choice[str], prize: str = "Fast Prize", duration: str = "1M", winners: int = 1):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)
    if mode.value == "fast":
        await interaction.response.send_message("Starting Fast Giveaway...", ephemeral=True)
        return await interaction.channel.send("⚡ **FAST GIVEAWAY!** First to click the button wins! ⚡", view=FastGiveawayView())

    try: duration_seconds = parse_duration(duration)
    except Exception: return await interaction.response.send_message("Invalid duration format! Use M, H, D, or MO.", ephemeral=True)

    view = GiveawayView()
    await interaction.response.send_message(f"Starting giveaway for '{prize}'...", ephemeral=True)
    msg = await interaction.channel.send(f"🎉 **GIVEAWAY** 🎉\n**Prize:** {prize}\n**Winners:** {winners}\nEnds in **{duration}**!", view=view)
    
    await asyncio.sleep(duration_seconds)
    
    if len(view.participants) == 0: await msg.reply("Giveaway ended, but nobody entered. 😢")
    else:
        actual_winners_count = min(winners, len(view.participants))
        chosen_winners = random.sample(list(view.participants), actual_winners_count)
        mentions = ", ".join(f"<@{w}>" for w in chosen_winners)
        await msg.reply(f"Congratulations {mentions}! You won **{prize}**! 🎉")

# ----------------------------------
TOKEN = os.getenv('TOKEN')
if __name__ == "__main__":
    bot.run(TOKEN)
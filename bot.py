import discord
from discord.ext import commands
from discord.ui import View
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import time

# =========================
# ENV
# =========================
load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

if not TOKEN or not MONGO_URI:
    raise Exception("TOKEN ou MONGO_URI não configurado no .env")

# =========================
# CONFIGURAÇÕES
# =========================
HIERARQUIA_CHANNEL_ID = 1499462619952578560

# =========================
# MONGO
# =========================
client = MongoClient(MONGO_URI)
db = client["discord"]

users = db["users"]

# =========================
# BOT
# =========================
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

active_calls = {}

# =========================
# RANKS
# =========================
RANKS = [
    {"name": "Recruta PMESC", "minutes": 180},
    {"name": "Soldado", "minutes": 600},
    {"name": "Cabo", "minutes": 720},
    {"name": "3º Sargento", "minutes": 1140},
    {"name": "2º Sargento", "minutes": 1560},
    {"name": "1º Sargento", "minutes": 1980},
    {"name": "Subtenente", "minutes": 2400},
    {"name": "Aspirante", "minutes": 2820},
    {"name": "2º Tenente", "minutes": 3240},
    {"name": "1º Tenente", "minutes": 3660},
    {"name": "Capitão", "minutes": 4080},
    {"name": "Major", "minutes": 4500},
    {"name": "Tenente-Coronel", "minutes": 4920},
    {"name": "Coronel", "minutes": 5340},
    {"name": "Comandante", "minutes": 5760},
]

# =========================
# FUNÇÕES
# =========================
def get_user(guild_id, user_id):
    user = users.find_one({"guild_id": guild_id, "user_id": user_id})

    if not user:
        user = {"guild_id": guild_id, "user_id": user_id, "total_time": 0}
        users.insert_one(user)

    return user


def get_rank(total_time):
    minutes = total_time / 60
    current = None

    for r in RANKS:
        if minutes >= r["minutes"]:
            current = r

    return current

# =========================
# VOICE SYSTEM
# =========================
@bot.event
async def on_voice_state_update(member, before, after):

    if not before.channel and after.channel:
        if len(after.channel.members) >= 2:
            active_calls[member.id] = time.time()

    if before.channel and not after.channel:
        start = active_calls.pop(member.id, None)

        if start:
            duration = time.time() - start

            users.update_one(
                {"guild_id": member.guild.id, "user_id": member.id},
                {"$inc": {"total_time": duration}},
                upsert=True
            )

# =========================
# READY (SEM HIERARQUIA AUTOMÁTICA)
# =========================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online como {bot.user}")

# =========================
# COMMANDS
# =========================
@tree.command(name="rank", description="Ver seu rank")
async def rank(interaction: discord.Interaction):

    await interaction.response.defer()

    u = get_user(interaction.guild.id, interaction.user.id)

    minutes = int(u["total_time"] / 60)
    rank_data = get_rank(u["total_time"])

    embed = discord.Embed(title="🎖️ Seu Rank", color=0x00ff00)

    embed.add_field(name="Tempo", value=f"{minutes} minutos", inline=False)
    embed.add_field(
        name="Patente",
        value=rank_data["name"] if rank_data else "Sem patente",
        inline=False
    )

    await interaction.followup.send(embed=embed)


@tree.command(name="top", description="Top militares")
async def top(interaction: discord.Interaction):

    await interaction.response.defer()

    data = list(
        users.find({"guild_id": interaction.guild.id})
        .sort("total_time", -1)
        .limit(10)
    )

    embed = discord.Embed(title="🏆 Ranking Militar", color=0xf1c40f)

    for i, u in enumerate(data):
        embed.add_field(
            name=f"{i+1}º Lugar",
            value=f"<@{u['user_id']}> - {int(u['total_time']/60)} min",
            inline=False
        )

    await interaction.followup.send(embed=embed)

# =========================
# PROMOÇÃO (BÁSICO)
# =========================
class PromocaoView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Solicitar Promoção", style=discord.ButtonStyle.green)
    async def btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            "Sistema de promoção ativo.",
            ephemeral=True
        )


@tree.command(name="painelpromocao", description="Painel de promoção")
async def painelpromocao(interaction: discord.Interaction):

    await interaction.response.defer()

    embed = discord.Embed(
        title="🎖️ PROMOÇÕES",
        description="Clique no botão abaixo para solicitar promoção",
        color=0x2b2d31
    )

    await interaction.followup.send(embed=embed, view=PromocaoView())

# =========================
# RUN
# =========================
bot.run(TOKEN)
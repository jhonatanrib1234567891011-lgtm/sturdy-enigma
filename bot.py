import discord
from discord.ext import commands
from discord.ui import View
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import time
import asyncio
from datetime import datetime

# =========================
# LOAD ENV
# =========================
load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# =========================
# CONFIGURAÇÕES
# =========================
HIERARQUIA_CHANNEL_ID = 1499462619952578560
ALLOWED_ROLE_ID = 1498760685394596047

PAINEL_PROMOCAO_CHANNEL_ID = 1499463150087569498
APROVACAO_PROMOCAO_CHANNEL_ID = 1501414515051335841

# CANAL ADM LOGS
CANAL_ADM_LOGS_ID = 1501414515051335841

# =========================
# MONGODB
# =========================
client = MongoClient(MONGO_URI)

db = client["discord"]

users = db["users"]
settings = db["settings"]

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()

intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

tree = bot.tree

active_calls = {}

# =========================
# PATENTES
# =========================
RANKS = [
    {"name": "Recruta PMESC", "minutes": 180, "role_id": 1498760685394596047},
    {"name": "Soldado", "minutes": 600, "role_id": 1498760685394596048},
    {"name": "Cabo", "minutes": 720, "role_id": 1498760685394596049},
    {"name": "3º Sargento", "minutes": 1140, "role_id": 1498760685394596050},
    {"name": "2º Sargento", "minutes": 1560, "role_id": 1498760685394596051},
    {"name": "1º Sargento", "minutes": 1980, "role_id": 1498760685406912724},
    {"name": "Subtenente", "minutes": 2400, "role_id": 1498760685406912725},
    {"name": "Aspirante", "minutes": 2820, "role_id": 1498760685406912731},
    {"name": "2º Tenente", "minutes": 3240, "role_id": 1498760685406912733},
    {"name": "1º Tenente", "minutes": 3660, "role_id": 1498760685440602142},
    {"name": "Capitão", "minutes": 4080, "role_id": 1498760685440602143},
    {"name": "Major", "minutes": 4500, "role_id": 1498760685440602144},
    {"name": "Tenente-Coronel", "minutes": 4920, "role_id": 1498760685440602145},
    {"name": "Coronel", "minutes": 5340, "role_id": 1498760685440602146},
    {"name": "Comandante", "minutes": 5760, "role_id": 1498760685440602150},
]

# =========================
# FUNÇÕES
# =========================
def get_user(guild_id, user_id):

    user = users.find_one({
        "guild_id": guild_id,
        "user_id": user_id
    })

    if not user:
        user = {
            "guild_id": guild_id,
            "user_id": user_id,
            "total_time": 0
        }

        users.insert_one(user)

    return user


def get_rank(total_time):

    minutes = total_time / 60

    current = None

    for r in RANKS:
        if minutes >= r["minutes"]:
            current = r

    return current


def get_hierarquia_message_id():

    data = settings.find_one({
        "_id": "hierarquia_message"
    })

    return data["message_id"] if data else None


def save_hierarquia_message_id(message_id):

    settings.update_one(
        {"_id": "hierarquia_message"},
        {
            "$set": {
                "message_id": message_id
            }
        },
        upsert=True
    )

# =========================
# HIERARQUIA
# =========================
async def atualizar_hierarquia():

    channel = bot.get_channel(HIERARQUIA_CHANNEL_ID)

    if not channel:
        return

    guild = channel.guild

    embed = discord.Embed(
        title="🎖️ HIERARQUIA PMESC",
        color=0x2b2d31
    )

    HIERARQUIA = [
        1499466851665842287,
        1498760685440602150,
        1498760685440602146,
        1498760685440602145,
        1498760685440602144,
        1498760685440602143,
        1498760685440602142,
        1498760685406912733,
        1498760685406912731,
        1498760685406912725,
        1498760685406912724,
        1498760685394596051,
        1498760685394596050,
        1498760685394596049,
        1498760685394596048,
        1498760685394596047
    ]

    for role_id in HIERARQUIA:

        role = guild.get_role(role_id)

        if not role:
            continue

        members = [
            m for m in guild.members
            if role in m.roles
        ]

        value = (
            "\n".join(
                [f"➡️ {m.mention}" for m in members]
            )
            if members
            else "➡️ Nenhum membro."
        )

        embed.add_field(
            name=f"{role.name} ({len(members)})",
            value=value,
            inline=False
        )

    try:

        message_id = get_hierarquia_message_id()

        if message_id:

            msg = await channel.fetch_message(message_id)

            await msg.edit(embed=embed)

        else:

            msg = await channel.send(embed=embed)

            save_hierarquia_message_id(msg.id)

    except discord.NotFound:

        msg = await channel.send(embed=embed)

        save_hierarquia_message_id(msg.id)


async def loop_hierarquia():

    await bot.wait_until_ready()

    while not bot.is_closed():

        await atualizar_hierarquia()

        await asyncio.sleep(60)

# =========================
# EVENTOS
# =========================
@bot.event
async def on_ready():

    await tree.sync()

    print(f"✅ Bot online como {bot.user}")

    bot.loop.create_task(loop_hierarquia())

    bot.add_view(AprovarPromocaoView())
    bot.add_view(PromocaoView())


@bot.event
async def on_voice_state_update(member, before, after):

    guild_id = member.guild.id

    # Entrou na call
    if not before.channel and after.channel:

        if len(after.channel.members) >= 2:

            active_calls[member.id] = time.time()

    # Saiu da call
    if before.channel and not after.channel:

        start = active_calls.pop(member.id, None)

        if start:

            duration = time.time() - start

            users.update_one(
                {
                    "guild_id": guild_id,
                    "user_id": member.id
                },
                {
                    "$inc": {
                        "total_time": duration
                    }
                },
                upsert=True
            )

# =========================
# COMANDOS
# =========================
@tree.command(name="rank", description="Ver seu rank")
async def rank(interaction: discord.Interaction):

    u = get_user(
        interaction.guild.id,
        interaction.user.id
    )

    minutes = int(u["total_time"] / 60)

    rank_data = get_rank(u["total_time"])

    rank_name = (
        rank_data["name"]
        if rank_data
        else "Sem patente"
    )

    embed = discord.Embed(
        title="🎖️ Seu Rank",
        color=0x00ff00
    )

    embed.add_field(
        name="⏱️ Tempo",
        value=f"{minutes} minutos",
        inline=False
    )

    embed.add_field(
        name="🏅 Patente",
        value=rank_name,
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@tree.command(name="top", description="Top militares")
async def top(interaction: discord.Interaction):

    data = list(
        users.find({
            "guild_id": interaction.guild.id
        }).sort(
            "total_time",
            -1
        ).limit(10)
    )

    embed = discord.Embed(
        title="🏆 Ranking Militar",
        color=0xf1c40f
    )

    for i, u in enumerate(data):

        embed.add_field(
            name=f"{i+1}º Lugar",
            value=f"<@{u['user_id']}> - {int(u['total_time']/60)} min",
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


@tree.command(name="hierarquia", description="Atualiza hierarquia")
async def hierarquia(interaction: discord.Interaction):

    await atualizar_hierarquia()

    await interaction.response.send_message(
        "✅ Hierarquia atualizada!",
        ephemeral=True
    )


@tree.command(name="mudaravatar", description="Muda avatar do bot")
async def mudaravatar(interaction: discord.Interaction):

    if not (
        interaction.user.guild_permissions.administrator
        or any(
            r.id == ALLOWED_ROLE_ID
            for r in interaction.user.roles
        )
    ):

        await interaction.response.send_message(
            "❌ Você não possui permissão.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        "📷 Envie uma imagem em até 60 segundos.",
        ephemeral=True
    )

    def check(m):
        return (
            m.author.id == interaction.user.id
            and m.attachments
        )

    try:

        msg = await bot.wait_for(
            "message",
            timeout=60.0,
            check=check
        )

        img = await msg.attachments[0].read()

        await bot.user.edit(avatar=img)

        await interaction.followup.send(
            "✅ Avatar alterado!"
        )

    except asyncio.TimeoutError:

        await interaction.followup.send(
            "⏰ Tempo esgotado."
        )

# =========================
# BOTÕES PROMOÇÃO
# =========================
class AprovarPromocaoView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Aprovar",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="aprovar_promocao"
    )
    async def aprovar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        embed = interaction.message.embeds[0]

        embed.color = 0x00ff00

        data_hora = datetime.now().strftime("%d/%m/%Y às %Hh%M")

        embed.add_field(
            name="STATUS",
            value=(
                f"✅ Promoção aprovada\n\n"
                f"👮 Aprovado por: {interaction.user.mention}\n"
                f"📅 Data/Hora: {data_hora}"
            ),
            inline=False
        )

        await interaction.message.edit(
            embed=embed,
            view=None
        )

        try:

            user_id = int(embed.footer.text)

            usuario = await bot.fetch_user(user_id)

            await usuario.send(
                f"""
✅ Sua promoção PMERJ foi aprovada

👮 Aprovado por:
{interaction.user.mention}

📅 Data/Hora:
{data_hora}
                """
            )

            canal_logs = bot.get_channel(CANAL_ADM_LOGS_ID)

            if canal_logs:

                log_embed = discord.Embed(
                    title="✅ PROMOÇÃO APROVADA",
                    color=0x00ff00
                )

                log_embed.description = (
                    f"{usuario.mention} teve sua promoção aprovada."
                )

                log_embed.add_field(
                    name="👮 Aprovado por",
                    value=interaction.user.mention,
                    inline=False
                )

                log_embed.add_field(
                    name="📅 Data/Hora",
                    value=data_hora,
                    inline=False
                )

                await canal_logs.send(embed=log_embed)

        except Exception as e:
            print(e)

        await interaction.response.send_message(
            "✅ Promoção aprovada!",
            ephemeral=True
        )

    @discord.ui.button(
        label="Recusar",
        style=discord.ButtonStyle.red,
        emoji="❌",
        custom_id="recusar_promocao"
    )
    async def recusar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "📝 Digite o motivo da reprovação no chat em até 60 segundos.",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id

        try:

            motivo_msg = await bot.wait_for(
                "message",
                timeout=60,
                check=check
            )

            motivo = motivo_msg.content

            embed = interaction.message.embeds[0]

            embed.color = 0xff0000

            data_hora = datetime.now().strftime("%d/%m/%Y às %Hh%M")

            embed.add_field(
                name="STATUS",
                value=(
                    f"❌ Promoção recusada\n\n"
                    f"📌 Motivo: {motivo}\n"
                    f"👮 Reprovado por: {interaction.user.mention}\n"
                    f"📅 Data/Hora: {data_hora}"
                ),
                inline=False
            )

            await interaction.message.edit(
                embed=embed,
                view=None
            )

            try:

                user_id = int(embed.footer.text)

                usuario = await bot.fetch_user(user_id)

                await usuario.send(
                    f"""
❌ Sua promoção PMERJ foi reprovada

📌 Motivo:
{motivo}

👮 Reprovado por:
{interaction.user.mention}

📅 Data/Hora:
{data_hora}
                    """
                )

                canal_logs = bot.get_channel(CANAL_ADM_LOGS_ID)

                if canal_logs:

                    log_embed = discord.Embed(
                        title="❌ PROMOÇÃO REPROVADA",
                        color=0xff0000
                    )

                    log_embed.description = (
                        f"{usuario.mention} teve sua promoção reprovada."
                    )

                    log_embed.add_field(
                        name="📌 Motivo",
                        value=motivo,
                        inline=False
                    )

                    log_embed.add_field(
                        name="👮 Reprovado por",
                        value=interaction.user.mention,
                        inline=False
                    )

                    log_embed.add_field(
                        name="📅 Data/Hora",
                        value=data_hora,
                        inline=False
                    )

                    await canal_logs.send(embed=log_embed)

            except Exception as e:
                print(e)

        except asyncio.TimeoutError:

            await interaction.followup.send(
                "⏰ Tempo esgotado.",
                ephemeral=True
            )

# =========================
# MODAL PROMOÇÃO
# =========================
class PromocaoModal(
    discord.ui.Modal,
    title="Solicitação de Promoção"
):

    nome = discord.ui.TextInput(
        label="👤 Nome",
        placeholder="Digite seu nome",
        required=True
    )

    user_id = discord.ui.TextInput(
        label="🆔 ID",
        placeholder="Digite seu ID",
        required=True
    )

    cargo_atual = discord.ui.TextInput(
        label="🎖 Cargo Atual",
        placeholder="Ex: Cabo",
        required=True
    )

    cargo_desejado = discord.ui.TextInput(
        label="⬆ Cargo Desejado",
        placeholder="Ex: Sargento",
        required=True
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        canal = bot.get_channel(
            APROVACAO_PROMOCAO_CHANNEL_ID
        )

        if not canal:

            await interaction.response.send_message(
                "❌ Canal não encontrado.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="📋 Solicitação de Promoção",
            color=0x2b2d31
        )

        embed.add_field(
            name="👤 Nome",
            value=self.nome.value,
            inline=False
        )

        embed.add_field(
            name="🆔 ID",
            value=self.user_id.value,
            inline=False
        )

        embed.add_field(
            name="🎖 Cargo Atual",
            value=self.cargo_atual.value,
            inline=False
        )

        embed.add_field(
            name="⬆ Cargo Desejado",
            value=self.cargo_desejado.value,
            inline=False
        )

        embed.set_thumbnail(
            url=interaction.user.display_avatar.url
        )

        embed.set_footer(
            text=str(interaction.user.id)
        )

        await canal.send(
            embed=embed,
            view=AprovarPromocaoView()
        )

        await interaction.response.send_message(
            "✅ Solicitação enviada!",
            ephemeral=True
        )

# =========================
# VIEW PROMOÇÃO
# =========================
class PromocaoView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Solicitar Promoção",
        style=discord.ButtonStyle.green,
        emoji="🎖️",
        custom_id="solicitar_promocao"
    )
    async def solicitar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            PromocaoModal()
        )

# =========================
# COMANDO PAINEL
# =========================
@tree.command(
    name="painelpromocao",
    description="Criar painel de promoção"
)
async def painelpromocao(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎖️ SISTEMA DE PROMOÇÃO",
        description=(
            "Clique no botão abaixo para "
            "solicitar sua promoção."
        ),
        color=0x2b2d31
    )

    await interaction.response.send_message(
        embed=embed,
        view=PromocaoView()
    )

import os

TOKEN = os.getenv("DISCORD_TOKEN")

bot.run(TOKEN)
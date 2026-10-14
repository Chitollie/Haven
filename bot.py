import asyncio
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('haven')

TOKEN = os.environ['DISCORD_TOKEN']
PANEL_URL = os.environ['PANEL_URL'].rstrip('/')
API_KEY = os.environ['PANEL_API_KEY']
SERVER_ID = os.environ['SERVER_ID']
CFX_JOIN_URL = 'https://cfx.re/join/7bbybqd'
CHANNEL_ID = int(os.environ['ANNOUNCE_CHANNEL_ID'])
FIVEM_INFO_URL = os.getenv('FIVEM_INFO_URL', 'http://gta-free01.arkya.host:30132/info.json')

if not PANEL_URL.startswith('https://'):
    raise ValueError('PANEL_URL doit utiliser HTTPS.')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
power_lock = asyncio.Lock()
last_ready = None

STATES = {
    'offline': '🔴 Hors ligne',
    'starting': '🟡 Démarrage',
    'running': '🟢 En ligne',
    'stopping': '🟠 Arrêt en cours',
}


async def api_request(method, endpoint, payload=None):
    url = f'{PANEL_URL}/api/client/servers/{SERVER_ID}/{endpoint}'

    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'Application/vnd.pterodactyl.v1+json',
        'Content-Type': 'application/json',
    }

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                url,
                headers=headers,
                json=payload
            ) as response:

                if response.status not in (200, 204):
                    log.error(
                        'API Arkya : erreur HTTP %s',
                        response.status
                    )

                    raise RuntimeError(
                        f'Erreur API Arkya HTTP {response.status}'
                    )

                if response.status == 204:
                    return {}

                return await response.json()

    except aiohttp.ClientError as error:
        log.error(
            'Connexion API Arkya impossible : %s',
            error
        )
        raise

    except asyncio.TimeoutError:
        log.error(
            'API Arkya : délai de connexion dépassé'
        )
        raise

async def get_status():
    data = await api_request('GET', 'resources')
    return data['attributes']['current_state']

async def is_ready():
    if await get_status() != 'running':
        return False
    timeout = aiohttp.ClientTimeout(total=6)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(FIVEM_INFO_URL) as response:
            if response.status != 200:
                return False
            data = await response.json(content_type=None)
            return isinstance(data, dict) and 'server' in data

async def start_server():
    async with power_lock:
        state = await get_status()
        if state != 'offline':
            return f'Haven est déjà dans cet état : {STATES.get(state, state)}.'
        await api_request('POST', 'power', {'signal': 'start'})
        return '🟡 Démarrage de Haven demandé. Une annonce sera envoyée dès que le serveur sera prêt.'

async def restart_server():
    async with power_lock:
        state = await get_status()
        if state != 'running':
            return f'Redémarrage impossible : {STATES.get(state, state)}.'
        await api_request('POST', 'power', {'signal': 'restart'})
        return '🔄 Redémarrage de Haven demandé.'

class HavenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label='Se connecter', emoji='🎮', style=discord.ButtonStyle.link, url=CFX_JOIN_URL))

    @discord.ui.button(label='Démarrer Haven', emoji='🟢', style=discord.ButtonStyle.success, custom_id='haven:start:v1')
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            message = await start_server()
        except Exception:
            log.exception('Erreur démarrage')
            message = '❌ Démarrage impossible. Consulte les logs du bot.'
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(label='État du serveur', emoji='📡', style=discord.ButtonStyle.secondary, custom_id='haven:status:v1')
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            state = await get_status()
            message = f'Haven : {STATES.get(state, state)}'
        except Exception:
            log.exception('Erreur statut')
            message = '❌ Statut indisponible.'
        await interaction.followup.send(message, ephemeral=True)

@bot.tree.command(name='start', description='Démarrer Haven')
async def start_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        message = await start_server()
    except Exception:
        log.exception('Erreur /start')
        message = '❌ Démarrage impossible.'
    await interaction.followup.send(message, ephemeral=True)

@bot.tree.command(name='status', description='Consulter le statut de Haven')
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        state = await get_status()
        message = f'Haven : {STATES.get(state, state)}'
    except Exception:
        log.exception('Erreur /status')
        message = '❌ Statut indisponible.'
    await interaction.followup.send(message, ephemeral=True)

@bot.tree.command(name='restart', description='Redémarrer Haven (administrateurs)')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def restart_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        message = await restart_server()
    except Exception:
        log.exception('Erreur /restart')
        message = '❌ Redémarrage impossible.'
    await interaction.followup.send(message, ephemeral=True)

@bot.tree.command(name='panel', description='Publier le panneau Haven (administrateurs)')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def panel_command(interaction: discord.Interaction):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message('Commande disponible uniquement dans un salon du serveur.', ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title='🎮 HAVEN RP',
        description='Bienvenue sur Haven ! Démarrez le serveur, consultez son état ou rejoignez-le avec les boutons ci-dessous.',
        color=discord.Color.from_rgb(108, 140, 255),
    )
    embed.set_footer(text='Haven RP • Inclusif et convivial')
    await interaction.channel.send(embed=embed, view=HavenView())
    await interaction.followup.send('✅ Panneau publié.', ephemeral=True)

@restart_command.error
@panel_command.error
async def admin_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        message = '❌ Cette commande est réservée aux administrateurs.'
    else:
        log.error('Erreur commande admin : %s', error)
        message = '❌ Une erreur est survenue.'
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)

@tasks.loop(seconds=20)
async def watch_haven():
    global last_ready
    try:
        ready = await is_ready()
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, KeyError, ValueError):
        log.warning('Surveillance Haven : serveur ou API inaccessible')
        return

    # Au lancement du bot, initialiser l'état sans annoncer une ouverture ancienne.
    if last_ready is None:
        last_ready = ready
        return
    if not ready:
        last_ready = False
        return
    if last_ready:
        return

    # Ne marquer comme annoncé qu'après un envoi réussi.
    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        embed = discord.Embed(
            title='🟢 HAVEN EST OUVERT !',
            description='Haven RP est prêt à accueillir les joueurs. Cliquez sur le bouton pour rejoindre le serveur.',
            color=discord.Color.green(),
        )
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label='Rejoindre Haven', emoji='🎮', style=discord.ButtonStyle.link, url=CFX_JOIN_URL))
        await channel.send(embed=embed, view=view)
        last_ready = True
    except (discord.DiscordException, AttributeError):
        log.exception('Impossible de publier l’annonce Haven')

@watch_haven.before_loop
async def before_watch_haven():
    await bot.wait_until_ready()

@bot.event
async def setup_hook():
    bot.add_view(HavenView())
    await bot.tree.sync()
    watch_haven.start()

@bot.event
async def on_ready():
    log.info('Bot Haven connecté : %s', bot.user)

bot.run(TOKEN)

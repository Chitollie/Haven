import asyncio
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import time
from datetime import time as dtime
from zoneinfo import ZoneInfo

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
intents.members = True
class HavenBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        self.add_view(HavenView())
        await community_setup(self)
        await self.tree.sync()
        watch_haven.start()
        daily_restart.start()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = HavenBot(command_prefix='!', intents=intents)
power_lock = asyncio.Lock()
last_ready = None

START_COOLDOWN = 180
MAX_FAILED_STARTS = 3
last_start_at = None
failed_starts = 0
auto_start_enabled = True
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
        'Accept': 'application/vnd.pterodactyl.v1+json',
        'Content-Type': 'application/json',
    }
    async with bot.session.request(method, url, headers=headers, json=payload) as response:
        if response.status not in (200, 204):
            log.error('API Arkya HTTP %s', response.status)
            raise RuntimeError('Erreur API Arkya')
        return {} if response.status == 204 else await response.json()

async def get_status():
    data = await api_request('GET', 'resources')
    return data['attributes']['current_state']

async def fivem_responds():
    try:
        async with bot.session.get(FIVEM_INFO_URL, timeout=aiohttp.ClientTimeout(total=6)) as response:
            if response.status != 200:
                return False
            data = await response.json(content_type=None)
            return isinstance(data, dict) and 'server' in data
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return False

def cooldown_active():
    return last_start_at is not None and time.monotonic() - last_start_at < START_COOLDOWN

async def start_server():
    """Renvoie (code, état) avec code = 'started', 'already' ou 'cooldown'."""
    global last_start_at
    async with power_lock:
        state = await get_status()
        if state != 'offline':
            return 'already', state
        if cooldown_active():
            return 'cooldown', state
        await api_request('POST', 'power', {'signal': 'start'})
        last_start_at = time.monotonic()
        return 'started', state

async def restart_server():
    global last_start_at
    async with power_lock:
        state = await get_status()
        if state != 'running':
            return f'Redémarrage impossible : {STATES.get(state, state)}.'
        await api_request('POST', 'power', {'signal': 'restart'})
        last_start_at = time.monotonic()
        return '🔄 Redémarrage de Haven demandé.'

class HavenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label='Se connecter', emoji='🎮', style=discord.ButtonStyle.link, url=CFX_JOIN_URL))

    #@discord.ui.button(label='Démarrer Haven', emoji='🟢', style=discord.ButtonStyle.success, custom_id='haven:start:v1')
    #async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        #await interaction.response.defer(ephemeral=True)
        #try:
            #message = await start_server()
        #except Exception:
            #log.exception('Erreur démarrage')
            #message = '❌ Démarrage impossible. Consulte les logs du bot.'
        #await interaction.followup.send(message, ephemeral=True)

    #@discord.ui.button(label='État du serveur', emoji='📡', style=discord.ButtonStyle.secondary, custom_id='haven:status:v1')
    #async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        #await interaction.response.defer(ephemeral=True)
        #try:
            #state = await get_status()
            #message = f'Haven : {STATES.get(state, state)}'
        #except Exception:
            #log.exception('Erreur statut')
            #message = '❌ Statut indisponible.'
        #await interaction.followup.send(message, ephemeral=True)

@bot.tree.command(name='start', description='Démarrer Haven')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def start_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        code, state = await start_server()
        if code == 'started':
            message = '🟡 Démarrage de Haven demandé. Une annonce sera envoyée dès que le serveur sera prêt.'
        elif code == 'cooldown':
            message = '⏳ Un démarrage vient d’être demandé, patiente quelques minutes.'
        else:
            message = f'Haven est déjà dans cet état : {STATES.get(state, state)}.'
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

@bot.tree.command(name='forcerestart', description='Forcer l’arrêt puis le démarrage de Haven')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def forcerestart_command(interaction: discord.Interaction):
    global auto_start_enabled, last_start_at
    await interaction.response.defer(ephemeral=True)
    if power_lock.locked():
        await interaction.followup.send('Une autre opération sur le serveur est en cours.', ephemeral=True)
        return
    async with power_lock:
        previous_auto = auto_start_enabled
        auto_start_enabled = False
        try:
            state = await get_status()
            if state != 'offline':
                await api_request('POST', 'power', {'signal': 'kill'})
                for _ in range(30):
                    await asyncio.sleep(2)
                    state = await get_status()
                    if state == 'offline':
                        break
                else:
                    await interaction.followup.send(
                        'Arrêt forcé demandé, mais Arkya ne confirme pas l’arrêt après 60 secondes. '
                        'Aucun démarrage lancé. Contacte le support Arkya.', ephemeral=True)
                    return
            await api_request('POST', 'power', {'signal': 'start'})
            last_start_at = time.monotonic()
            await interaction.followup.send(
                'Redémarrage demandé à Arkya. Vérifie la console pour confirmer le démarrage.',
                ephemeral=True)
        except Exception:
            log.exception('Erreur /forcerestart')
            await interaction.followup.send(
                'Échec de la commande API Arkya. Vérifie les logs du bot et le panel.',
                ephemeral=True)
        finally:
            auto_start_enabled = previous_auto

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
        description='Bienvenue sur Haven ! Rejoignez-le avec le boutons ci-dessous.',
        color=discord.Color.from_rgb(108, 140, 255),
    )
    embed.set_footer(text='Haven RP • Inclusif et convivial')
    await interaction.channel.send(embed=embed, view=HavenView())
    await interaction.followup.send('✅ Panneau publié.', ephemeral=True)

@bot.tree.command(name='auto', description='Activer ou couper la relance automatique (administrateurs)')
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(actif='True = relance automatique, False = mode maintenance')
async def auto_command(interaction: discord.Interaction, actif: bool):
    global auto_start_enabled, failed_starts
    auto_start_enabled = actif
    failed_starts = 0
    etat = 'activée' if actif else 'désactivée (maintenance)'
    await interaction.response.send_message(f'✅ Relance automatique {etat}.', ephemeral=True)

@start_command.error
@auto_command.error
@restart_command.error
@forcerestart_command.error
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
        
async def try_auto_start():
    global failed_starts, auto_start_enabled
    if cooldown_active():
        return
    if failed_starts >= MAX_FAILED_STARTS:
        auto_start_enabled = False
        log.error('Relance auto désactivée : %s démarrages sans succès', failed_starts)
        return
    code, _ = await start_server()
    if code == 'started':
        failed_starts += 1
        log.info('Relance auto demandée (essai %s/%s)', failed_starts, MAX_FAILED_STARTS)

PARIS = ZoneInfo('Europe/Paris')

@tasks.loop(time=dtime(hour=6, minute=0, tzinfo=PARIS))
async def daily_restart():
    try:
        message = await restart_server()
        log.info('Redémarrage quotidien : %s', message)
    except Exception:
        log.exception('Redémarrage quotidien échoué')

@daily_restart.before_loop
async def before_daily_restart():
    await bot.wait_until_ready()
    
@tasks.loop(seconds=20)
async def watch_haven():
    global last_ready, failed_starts
    try:
        state = await get_status()
        ready = state == 'running' and await fivem_responds()
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, KeyError):
        log.warning('Surveillance Haven : API du panel inaccessible')
        return
    except Exception:
        log.exception('Surveillance Haven : erreur inattendue')
        return

    # Relance automatique
    if state == 'running':
        failed_starts = 0
    elif state == 'offline' and auto_start_enabled:
        try:
            await try_auto_start()
        except Exception:
            log.exception('Relance automatique échouée')

    if last_ready is None:
        last_ready = ready
        return
    if not ready:
        last_ready = False
        return
    if last_ready:
        return

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
async def on_ready():
    log.info('Bot Haven connecté : %s', bot.user)

from community import setup as community_setup
bot.run(TOKEN)

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

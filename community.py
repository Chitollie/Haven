"""Haven RP community features for discord.py 2.x."""
import asyncio
import os
import re
import discord
from discord import app_commands
from discord.ext import commands

WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID', '0'))
MEMBER_ROLE_ID = int(os.getenv('MEMBER_ROLE_ID', '0'))
STAFF_ROLE_ID = int(os.getenv('STAFF_ROLE_ID', '0'))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID', '0'))
ACCENT = discord.Color.from_rgb(108, 140, 255)
FOOTER = 'Haven RP • Inclusif et convivial'

def embed(title, description, color=ACCENT):
    result = discord.Embed(title=title, description=description, color=color)
    result.set_footer(text=FOOTER)
    return result

def staff_only():
    async def predicate(interaction):
        if not isinstance(interaction.user, discord.Member):
            return False
        return interaction.user.guild_permissions.administrator or (STAFF_ROLE_ID and any(role.id == STAFF_ROLE_ID for role in interaction.user.roles))
    return app_commands.check(predicate)

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Fermer le ticket', emoji='🔒', style=discord.ButtonStyle.danger, custom_id='haven:ticket:close')
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not channel.topic or not channel.topic.startswith('haven-ticket:'):
            await interaction.response.send_message('Ce salon n’est pas un ticket Haven.', ephemeral=True)
            return
        owner_id = int(channel.topic.split(':', 1)[1])
        member = interaction.user
        is_staff = isinstance(member, discord.Member) and (member.guild_permissions.administrator or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles)))
        if member.id != owner_id and not is_staff:
            await interaction.response.send_message('Tu ne peux pas fermer ce ticket.', ephemeral=True)
            return
        await interaction.response.send_message('🔒 Fermeture du ticket…', ephemeral=True)
        await channel.delete(reason=f'Ticket fermé par {member} ({member.id})')

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Ouvrir un ticket', emoji='🎫', style=discord.ButtonStyle.primary, custom_id='haven:ticket:open')
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message('Disponible uniquement sur Haven.', ephemeral=True)
            return
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message('Catégorie tickets non configurée. Contacte un administrateur.', ephemeral=True)
            return
        staff_role = guild.get_role(STAFF_ROLE_ID)
        if staff_role is None:
            await interaction.response.send_message('Rôle staff non configuré. Contacte un administrateur.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        # Scan by topic rather than name, so renamed tickets are still detected.
        for channel in guild.text_channels:
            if channel.topic == f'haven-ticket:{member.id}':
                await interaction.followup.send(f'Tu as déjà un ticket : {channel.mention}', ephemeral=True)
                return
        perms = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
        }
        try:
            channel = await guild.create_text_channel(
                name=f'ticket-{member.id}', category=category,
                overwrites=perms, topic=f'haven-ticket:{member.id}',
                reason=f'Ticket ouvert par {member} ({member.id})'
            )
            await channel.send(
                content=f'{member.mention} • {staff_role.mention}',
                embed=embed('🎫 SUPPORT HAVEN', 'Explique ton problème ici. Un membre du staff te répondra dès que possible.'),
                view=CloseTicketView(),
                allowed_mentions=discord.AllowedMentions(users=True, roles=True)
            )
            await interaction.followup.send(f'✅ Ticket créé : {channel.mention}', ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send('❌ Il manque des permissions au bot (gérer les salons / voir la catégorie).', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('❌ Impossible de créer le ticket pour le moment.', ephemeral=True)
            
TOUCHES = {
    'accueil': ('⌨️ TOUCHES ESSENTIELLES • HAVEN RP',
        '**Déplacements et menus**\n'
        '• `Z Q S D` : se déplacer (AZERTY)\n'
        '• `Échap` : menu pause Haven\n'
        '• `T` : chat (raccourci GTA habituel, à vérifier)\n'
        '• `Tab` : inventaire / ox_target (conflit)\n'
        '• `W` : menu radial ox_lib\n'
        '• `F1` : téléphone Sky Phone\n'
        '• `F12` : activer / couper le micro\n'
        '• `F11` : portée de la voix\n'
        '• `Alt` : parler à la radio\n'
        '• `F5` : menu des emotes / bodycam (conflit)\n'
        '\n**Attention :** plusieurs ressources utilisent les mêmes touches. '
        'Vous pouvez modifier les raccourcis dans les paramètres FiveM.'),
    'general': ('🎮 GÉNÉRAL',
        '• `Échap` : menu pause Haven\n• `W` : menu radial ox_lib\n'
        '• `Tab` : inventaire / ox_target (conflit)\n'
        '• `F3` : interface carburant\n• `F10` : administration Gowhord\n'
        '• `Maj G` : pousser un véhicule\n• `O` : changer de siège\n'
        '• `K` : s’accroupir\n• `E` : interaction ascenseur / pousser / plaquer (selon contexte)'),
    'vehicules': ('🚗 VÉHICULES',
        '• `Y` : moteur (gowhord_vehicle)\n• `B` : ceinture\n'
        '• `←` : clignotant gauche\n• `→` : clignotant droit\n'
        '• `↓` : feux de détresse\n• `J` : régulateur de vitesse\n'
        '• `F9` : radio du véhicule\n• `L` : verrouiller / déverrouiller\n'
        '• `H` : chercher les clés\n• `O` : changer de siège\n'
        '• `E` / `Maj G` : pousser un véhicule'),
    'police': ('🚓 POLICE ET SECOURS',
        '• `F6` : menu métier police / vue bodycam (conflit)\n'
        '• `F4` : lecteur de plaques\n'
        '• `F5` : activer / désactiver la bodycam (conflit emotes)\n'
        '• `R` : réapparition ambulance lorsque disponible\n'
        '• `R` : recharger une arme (conflit contextuel)'),
    'inventaire': ('🎒 INVENTAIRE',
        '• `Tab` : ouvrir l’inventaire / ox_target (conflit)\n'
        '• `L` : inventaire secondaire (conflit verrouillage)\n'
        '• `R` : recharger une arme\n'
        '• `&` : objet rapide 1\n• `é` : objet rapide 2\n'
        '• `"` : objet rapide 3\n• `\'` : objet rapide 4\n'
        '• `(` : objet rapide 5'),
    'interactions': ('🤝 INTERACTIONS',
        '• `Tab` : ox_target (conflit inventaire)\n'
        '• `W` : menu radial\n'
        '• `Y` : accepter une demande (conflit moteur)\n'
        '• `N` : refuser une demande\n'
        '• `X` : arrêter une interaction / se relever\n'
        '• `E` : interactions contextuelles\n'
        '• `G` : menu de production Central Distribution (selon proximité)'),
    'emotes': ('🎭 EMOTES',
        '• `F5` : menu des emotes\n• `X` : annuler une emote\n'
        '• `G` : effet d’emote\n• `H` : mains en l’air\n'
        '• `B` : pointer\n• `Ctrl G` : posture\n'
        '• `U` : tomber\n'
        '• Raccourcis d’emotes 1 à 6 : touches non attribuées sur les captures'),
    'communication': ('🎙️ COMMUNICATION',
        '• `F12` : couper / activer le micro Haven\n'
        '• `F11` : changer la portée vocale\n'
        '• `Alt` : parler à la radio\n'
        '• `+` (pavé numérique) : push-to-talk secondaire\n'
        '• `F1` : téléphone Sky Phone\n'
        '• `5` (pavé numérique) : ping CrewLink\n'
        '• `T` : ouvrir le chat (raccourci habituel à vérifier)'),
    'administration': ('🛡️ ADMINISTRATION',
        '• `F10` : ouvrir Gowhord Admin\n'
        '• `F6` : menu police (si métier autorisé)\n'
        '• `G` : Central Distribution, point de production (si autorisé)\n'
        '• `Noclip` : raccourci affiché par FiveM, à vérifier dans les paramètres'),
}

class TouchesSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Accueil', value='accueil', emoji='🏠'),
            discord.SelectOption(label='Général', value='general', emoji='🎮'),
            discord.SelectOption(label='Véhicules', value='vehicules', emoji='🚗'),
            discord.SelectOption(label='Police et secours', value='police', emoji='🚓'),
            discord.SelectOption(label='Inventaire', value='inventaire', emoji='🎒'),
            discord.SelectOption(label='Interactions', value='interactions', emoji='🤝'),
            discord.SelectOption(label='Emotes', value='emotes', emoji='🎭'),
            discord.SelectOption(label='Communication', value='communication', emoji='🎙️'),
            discord.SelectOption(label='Administration', value='administration', emoji='🛡️'),
        ]
        super().__init__(
            placeholder='Choisir une catégorie de touches…',
            min_values=1,
            max_values=1,
            options=options,
            custom_id='haven:touches:category'
        )

    async def callback(self, interaction: discord.Interaction):
        title, description = TOUCHES[self.values[0]]

        if interaction.message.flags.ephemeral:
            await interaction.response.edit_message(
                embed=embed(title, description),
                view=TouchesView()
            )
        else:
            await interaction.response.send_message(
                embed=embed(title, description),
                view=TouchesView(),
                ephemeral=True
            )
class TouchesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TouchesSelect())

    @discord.ui.button(label='Accueil', emoji='🏠', style=discord.ButtonStyle.secondary,
                       custom_id='haven:touches:home', row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        title, description = TOUCHES['accueil']
        await interaction.response.edit_message(embed=embed(title, description), view=TouchesView())

async def setup(bot: commands.Bot):
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())
    bot.add_view(TouchesView())

    @bot.event
    async def on_member_join(member: discord.Member):
        if MEMBER_ROLE_ID:
            role = member.guild.get_role(MEMBER_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role, reason='Rôle automatique Haven')
                except discord.Forbidden:
                    pass
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=embed('👋 BIENVENUE SUR HAVEN', f'Bienvenue {member.mention} ! 💜\n\nHaven RP est un espace convivial, inclusif et sans pression. Prends le temps de découvrir le règlement et de rejoindre la communauté.\n\n**Membre n° {member.guild.member_count}**'))
            except discord.Forbidden:
                pass

    @bot.tree.command(name='reglement', description='Publier le règlement de Haven RP')
    @app_commands.guild_only()
    @staff_only()
    async def reglement(interaction: discord.Interaction):
        # Modèle à personnaliser avant publication.
        rules = ('**1. Respect et bienveillance**\nAucun harcèlement, propos discriminatoire ou attaque personnelle.\n\n'
                 '**2. RP accessible à tous**\nRespectez le rythme, les limites et les besoins des autres joueurs.\n\n'
                 '**3. Fair-play**\nPas de triche, d’exploitation de bugs ou d’abus de mécaniques.\n\n'
                 '**4. Communication**\nEn cas de problème, contactez le staff via un ticket.\n\n'
                 '**5. Règles RP détaillées**\n*À compléter avec vos règles de scènes, métiers, criminalité et sanctions.*')
        await interaction.response.send_message('📜 Règlement publié.', ephemeral=True)
        await interaction.channel.send(embed=embed('📜 RÈGLEMENT • HAVEN RP', rules))

    @bot.tree.command(name='annonces', description='Publier une annonce officielle Haven')
    @app_commands.guild_only()
    @staff_only()
    @app_commands.describe(titre='Titre de l’annonce', message='Contenu de l’annonce')
    async def annonces(interaction: discord.Interaction, titre: str, message: str):
        if len(titre) > 200 or len(message) > 4000:
            await interaction.response.send_message('❌ Titre ou message trop long.', ephemeral=True)
            return
        await interaction.response.send_message('📢 Annonce publiée.', ephemeral=True)
        await interaction.channel.send(embed=embed(f'📢 {titre}', message), allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(name='ticketpanel', description='Publier le panneau de tickets')
    @app_commands.guild_only()
    @staff_only()
    async def ticketpanel(interaction: discord.Interaction):
        await interaction.response.send_message('🎫 Panneau publié.', ephemeral=True)
        await interaction.channel.send(embed=embed('🎫 BESOIN D’AIDE ?', 'Une question, un problème ou un signalement ?\n\nClique sur **Ouvrir un ticket** pour discuter dans un salon privé avec le staff.'), view=TicketPanelView())

    @bot.tree.command(name='touches', description='Publier le guide des touches Haven RP')
    @app_commands.guild_only()
    @staff_only()
    async def touches(interaction: discord.Interaction):
        await interaction.response.send_message('⌨️ Guide publié.', ephemeral=True)
        title, description = TOUCHES['accueil']
        await interaction.channel.send(
            embed=embed(title, description),
            view=TouchesView()
        )

    @bot.tree.error
    async def community_errors(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            message = '❌ Commande réservée au staff Haven.'
        else:
            message = '❌ Une erreur est survenue. Consulte la console du bot.'
            import logging
            logging.getLogger('haven').error('Commande Discord : %r', error)
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

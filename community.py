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

async def setup(bot: commands.Bot):
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())

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
        guide = ('**Touches GTA / FiveM courantes**\n'
                 '• `W` : menu des interactions GTA\n'
                 '• `T` : ouvrir le chat\n'
                 '• `Échap` : menu pause\n\n'
                 '**Touches spécifiques à Haven**\n'
                 '• Inventaire : **I**\n'
                 '• Téléphone : **F1**\n'
                 '• Interaction / cible : **Tab / E**\n'
                 '• Radio : ****\n'
                 '• Menu personnage : ****\n\n'
                 '*Les raccourcis peuvent être modifiés dans les paramètres FiveM.*')
        await interaction.response.send_message('⌨️ Guide publié.', ephemeral=True)
        await interaction.channel.send(embed=embed('⌨️ TOUCHES • HAVEN RP', guide))

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

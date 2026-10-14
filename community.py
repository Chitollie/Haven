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


    @bot.tree.command(
        name='reglement',
        description='Publier le règlement de Haven RP'
    )
    @app_commands.guild_only()
    @staff_only()
    async def reglement(interaction: discord.Interaction):

        rules_pages = [
            (
                "🤝 1. Respect et vie communautaire",
                "**1.1 • Respect mutuel**\n"
                "Respectez tous les membres, quelle que soit leur expérience, leur identité ou leurs particularités.\n\n"
                "**1.2 • Harcèlement et discrimination**\n"
                "Tout harcèlement, discrimination, menace réelle ou attaque personnelle est interdit.\n\n"
                "**1.3 • Inclusion**\n"
                "Haven accueille les joueurs débutants, neurodivergents et en situation de handicap. Respectez les besoins et le rythme de chacun.\n\n"
                "**1.4 • Vie privée**\n"
                "Ne divulguez jamais les informations personnelles d'autrui sans son accord.\n\n"
                "**1.5 • Conflits**\n"
                "Les conflits HRP doivent être réglés calmement, si nécessaire avec le staff."
            ),
            (
                "🎭 2. Règles fondamentales du RP",
                "**2.1 • Metagaming**\n"
                "Interdiction d'utiliser en RP des informations obtenues hors RP.\n\n"
                "**2.2 • Powergaming**\n"
                "Interdiction d'imposer des actions irréalistes ou de forcer les réactions d'autrui.\n\n"
                "**2.3 • Fear RP**\n"
                "Votre personnage doit réagir de manière cohérente face au danger.\n\n"
                "**2.4 • Pain RP**\n"
                "Les blessures et leurs conséquences doivent être interprétées de manière cohérente.\n\n"
                "**2.5 • RDM / VDM**\n"
                "Toute agression injustifiée ou utilisation abusive d'un véhicule contre un joueur est interdite.\n\n"
                "**2.6 • Revenge Kill**\n"
                "Il est interdit de revenir se venger en utilisant des souvenirs que votre personnage a perdus.\n\n"
                "**2.7 • Combat Logging**\n"
                "Se déconnecter volontairement pour échapper à une scène RP est interdit."
            ),
            (
                "🧩 3. Accessibilité et consentement",
                "**3.1 • Bien-être des joueurs**\n"
                "Le confort réel des joueurs passe toujours avant l'immersion RP.\n\n"
                "**3.2 • Droit à la pause**\n"
                "Chaque joueur peut demander une pause HRP si une scène devient trop intense.\n\n"
                "**3.3 • Scènes sensibles**\n"
                "Les situations sensibles ne doivent jamais être imposées à un joueur.\n\n"
                "**3.4 • Contenus interdits**\n"
                "Les scènes sexuelles explicites et les comportements discriminatoires sont interdits.\n\n"
                "**3.5 • Communication adaptée**\n"
                "Les demandes de reformulation, d'explication ou de ralentissement doivent être respectées."
            ),
            (
                "🚗 4. Véhicules et conduite",
                "**4.1 • Conduite RP**\n"
                "Adoptez une conduite cohérente avec les circonstances.\n\n"
                "**4.2 • Accidents**\n"
                "Les accidents importants doivent entraîner des conséquences RP adaptées.\n\n"
                "**4.3 • Véhicules professionnels**\n"
                "Respectez l'utilisation prévue des véhicules de service.\n\n"
                "**4.4 • Vols**\n"
                "Les vols de véhicules doivent être justifiés par une situation RP.\n\n"
                "**4.5 • Exploitation**\n"
                "Toute exploitation de bugs ou de mécaniques pour obtenir un avantage est interdite."
            ),
            (
                "🚓 5. Services publics et métiers",
                "**5.1 • Respect des métiers**\n"
                "Les policiers, secouristes et employés doivent exercer leurs fonctions avec cohérence.\n\n"
                "**5.2 • Corruption**\n"
                "La corruption des services publics nécessite l'autorisation du staff.\n\n"
                "**5.3 • Interventions**\n"
                "Laissez aux services publics la possibilité de développer leurs scènes RP.\n\n"
                "**5.4 • RP médical**\n"
                "Respectez les prises en charge médicales et les conséquences de vos blessures.\n\n"
                "**5.5 • Abus de fonction**\n"
                "L'utilisation abusive d'un métier pour obtenir des avantages personnels est interdite."
            ),
            (
                "💼 6. Entreprises et économie",
                "**6.1 • Entreprises**\n"
                "Toute création d'entreprise doit respecter les procédures du serveur.\n\n"
                "**6.2 • Employés**\n"
                "Les dirigeants doivent favoriser un environnement de travail RP respectueux.\n\n"
                "**6.3 • Économie**\n"
                "La duplication d'objets, les abus financiers et l'exploitation de bugs sont interdits.\n\n"
                "**6.4 • Transactions**\n"
                "Les échanges doivent respecter les mécaniques et la cohérence RP.\n\n"
                "**6.5 • Activité**\n"
                "Les entreprises doivent favoriser les interactions plutôt que l'accumulation excessive de richesse."
            ),
            (
                "🔒 7. Criminalité et scènes illégales",
                "**7.1 • Justification**\n"
                "Toute activité illégale doit avoir une motivation RP cohérente.\n\n"
                "**7.2 • Braquages**\n"
                "Les braquages doivent laisser une possibilité raisonnable d'interaction aux participants.\n\n"
                "**7.3 • Prises d'otages**\n"
                "Les prises d'otages ne doivent jamais servir à humilier ou harceler un joueur.\n\n"
                "**7.4 • Ciblage abusif**\n"
                "Il est interdit de cibler systématiquement un personnage pour l'empêcher de jouer.\n\n"
                "**7.5 • Organisations**\n"
                "Les organisations criminelles structurées nécessitent une validation du staff.\n\n"
                "**7.6 • Fair-play**\n"
                "Le RP illégal ne permet pas de contourner les autres règles."
            ),
            (
                "👤 8. Personnages et identité",
                "**8.1 • Identité**\n"
                "Chaque personnage doit posséder une identité cohérente avec l'univers RP.\n\n"
                "**8.2 • Multipersonnages**\n"
                "Les transferts abusifs d'argent, d'objets ou d'informations entre vos personnages sont interdits.\n\n"
                "**8.3 • Mort RP définitive**\n"
                "Elle nécessite l'accord préalable du joueur concerné et du staff.\n\n"
                "**8.4 • Usurpation**\n"
                "Les usurpations d'identité doivent respecter les règles et mécaniques RP.\n\n"
                "**8.5 • Personnages perturbateurs**\n"
                "Les personnages créés uniquement pour perturber le serveur peuvent être refusés."
            ),
            (
                "💬 9. Discord et communication",
                "**9.1 • Salons**\n"
                "Respectez le thème et l'utilisation de chaque salon.\n\n"
                "**9.2 • Spam**\n"
                "Le flood, les mentions abusives et les perturbations volontaires sont interdits.\n\n"
                "**9.3 • Publicité**\n"
                "Toute publicité nécessite l'autorisation du staff.\n\n"
                "**9.4 • Vocal**\n"
                "Évitez les cris, sons excessifs et perturbations répétées.\n\n"
                "**9.5 • Vie privée**\n"
                "Respectez la confidentialité des échanges et les règles applicables aux enregistrements.\n\n"
                "**9.6 • Tickets**\n"
                "Utilisez les tickets pour les demandes d'assistance et les signalements sérieux."
            ),
            (
                "🛡️ 10. Staff et sanctions",
                "**10.1 • Staff**\n"
                "Le staff accompagne les joueurs et veille au respect du règlement.\n\n"
                "**10.2 • Impartialité**\n"
                "Les décisions doivent être prises de manière équitable.\n\n"
                "**10.3 • Contestations**\n"
                "Vous pouvez contester calmement une décision via un ticket.\n\n"
                "**10.4 • Abus**\n"
                "Tout abus de pouvoir peut être signalé à la direction.\n\n"
                "**10.5 • Sanctions**\n"
                "Selon la gravité : rappel, avertissement, restriction, exclusion temporaire ou bannissement définitif.\n\n"
                "**10.6 • Modifications**\n"
                "Le règlement peut évoluer. Les changements importants seront annoncés."
            ),
            (
                "💚 11. L'esprit Haven",
                "**🤝 Respect** • Traitez chacun avec dignité.\n\n"
                "**🌿 Bienveillance** • Les erreurs sont des occasions d'apprendre.\n\n"
                "**🧩 Inclusion** • Les différences ne doivent pas empêcher de participer.\n\n"
                "**🎭 Créativité** • Le RP est une histoire collective, pas une compétition.\n\n"
                "**💬 Communication** • Exprimez vos difficultés avec respect.\n\n"
                "**✅ Acceptation**\n"
                "En participant à Haven RP, vous acceptez le règlement et vous engagez à le respecter.\n\n"
                "*Haven RP • Votre histoire, votre rythme, votre place.*"
            )
        ]

        if interaction.channel is None:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un salon.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            for index, (title, description) in enumerate(
                rules_pages,
                start=1
            ):
                rule_embed = discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.from_rgb(93, 174, 142)
                )

                rule_embed.set_footer(
                    text=(
                        f"Haven RP • Règlement officiel "
                        f"• {index}/{len(rules_pages)}"
                    )
                )

                await interaction.channel.send(
                    embed=rule_embed
                )

            await interaction.followup.send(
                "✅ Les 11 sections du règlement ont été publiées.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission d'envoyer "
                "des messages ou des embeds dans ce salon.",
                ephemeral=True
            )

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Une erreur Discord est survenue "
                "pendant la publication du règlement.",
                ephemeral=True
            )


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

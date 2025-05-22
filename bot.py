import re
from collections import defaultdict
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import time
import os
import random
import json
import youtube_dl


# ───── Vorbereitung ─────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")

    await bot.tree.sync()

    tempvoice_category_id = 1365036730952061029

    ausnahmen = [
        1365036282291683419,
        1365312074833723513,
        1367877092649467944,
        1367877166271954965,
        1367877214254796962,
    ]

    category = bot.get_channel(tempvoice_category_id)

    if category and isinstance(category, discord.CategoryChannel):
        for channel in category.voice_channels:
            if channel.id not in ausnahmen:
                try:
                    await channel.delete()
                    print(f"🗑️ TempVoice gelöscht: {channel.name}")
                except Exception as e:
                    print(f"❌ Fehler beim Löschen von {channel.name}: {e}")
            else:
                print(f"⏭️ Ausgelassen (Ausnahmeliste): {channel.name}")

    await post_all_commands(bot)

class SlashCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# ───── Moderation ─────
class Moderation(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        await ctx.channel.purge(limit=amount)
        msg = await ctx.send(f"🧹 {amount} gelöscht.")
        await asyncio.sleep(3)
        await msg.delete()

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="Kein Grund"):
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member} wurde gebannt. Grund: {reason}")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="Kein Grund"):
        await member.kick(reason=reason)
        await ctx.send(f"🥾 {member} wurde gekickt. Grund: {reason}")

# ───── Allgemeine Befehle ─────
class General(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="ping", description="Zeigt die Bot-Latenz an")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! {latency}ms", ephemeral=True)

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"👤 Info zu {member}", color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="Username", value=member.name)
        embed.add_field(name="Beigetreten", value=member.joined_at.strftime("%d.%m.%Y"))
        embed.add_field(name="Erstellt am", value=member.created_at.strftime("%d.%m.%Y"))
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        g = ctx.guild
        embed = discord.Embed(title=f"🌐 {g.name}", color=discord.Color.green())
        embed.add_field(name="Mitglieder", value=g.member_count)
        embed.add_field(name="Erstellt", value=g.created_at.strftime("%d.%m.%Y"))
        embed.add_field(name="Besitzer", value=g.owner.mention)
        await ctx.send(embed=embed)

# ───── Spiele ─────
class Games(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command()
    async def guess(self, ctx):
        number = random.randint(1, 10)
        await ctx.send("Rate eine Zahl zwischen 1 und 10! Du hast 3 Versuche.")
        def check(m): return m.author.id == ctx.author.id and m.channel == ctx.channel
        for _ in range(3):
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=30)
                if int(msg.content) == number:
                    await ctx.send(f"🎉 Richtig geraten: {number}")
                    return
                else:
                    await ctx.send("❌ Falsch, nochmal!")
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ Zeit abgelaufen! Die Zahl war {number}.")
                return
        await ctx.send(f"😢 Leider verloren! Die Zahl war {number}.")

    @commands.command()
    async def dice(self, ctx):
        result = random.randint(1, 6)
        await ctx.send(f"🎲 Du hast eine **{result}** gewürfelt!")

# ───── Levelsystem ─────
class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.file = "levels.json"
        self.data = self.load()

    def load(self):
        return json.load(open(self.file)) if os.path.exists(self.file) else {}

    def save(self):
        json.dump(self.data, open(self.file, "w"), indent=4)

    def add_xp(self, uid, xp):
        uid = str(uid)
        self.data.setdefault(uid, {"xp": 0, "level": 1})
        self.data[uid]["xp"] += xp
        new_lvl = int(self.data[uid]["xp"] ** 0.25)
        if new_lvl > self.data[uid]["level"]:
            self.data[uid]["level"] = new_lvl
            return new_lvl
        return None

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot: return
        xp = random.randint(5, 15)
        lvl = self.add_xp(msg.author.id, xp)
        if lvl:
            await msg.channel.send(f"🎉 {msg.author.mention} ist jetzt Level {lvl}!")
        self.save()

    @commands.command()
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        uid = str(member.id)
        stats = self.data.get(uid)
        if stats:
            await ctx.send(f"🏅 {member.mention}: Level {stats['level']} mit {stats['xp']} XP.")
        else:
            await ctx.send("Noch keine XP gesammelt.")

# ───── Support ─────
class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1364928906934751293
        self.cooldowns = {}

    @commands.Cog.listener()
    async def on_ready(self):
        await self.setup_support_channel()

    async def setup_support_channel(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.purge()
            embed = discord.Embed(
                title="🎟️ Support-Ticket-System",
                description="Klicke auf **Ticket erstellen**, um dein Anliegen einzureichen.",
                color=discord.Color.orange()
            )
            view = TicketView(self.bot)
            await channel.send(embed=embed, view=view)

class TicketModal(discord.ui.Modal, title="🎫 Support-Anfrage"):
    def __init__(self, bot, user):
        super().__init__()
        self.bot = bot
        self.user = user

        self.thing = discord.ui.TextInput(
            label="Was ist dein Anliegen?",
            style=discord.TextStyle.paragraph,
            placeholder="Beschreibe hier dein Problem...",
            required=True,
            max_length=500
        )
        self.add_item(self.thing)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        support_role = guild.get_role(1364923879138660363)
        if not support_role:
            await interaction.response.send_message("❌ Die Support-Rolle konnte nicht gefunden werden.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True),
        }

        category = discord.utils.get(guild.categories, id=1364929679273754665)
        if not category:
            await interaction.response.send_message("❌ Die Support-Kategorie konnte nicht gefunden werden.", ephemeral=True)
            return

        # Channel erstellen
        channel = await guild.create_text_channel(
            name=f"ticket-{self.user.name}",
            overwrites=overwrites,
            category=category
        )

        embed = discord.Embed(
            title="🎫 Neues Ticket",
            description=f"**Anliegen:**\n{self.thing.value}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Nutze die Buttons unten.")
        view = TicketControls(self.bot, self.user)
        await channel.send(content=f"{self.user.mention}", embed=embed, view=view)

        await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Ticket erstellen", style=discord.ButtonStyle.green, emoji="🎟️")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketModal(self.bot, interaction.user)
        await interaction.response.send_modal(modal)

class TicketControls(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    @discord.ui.button(label="Mod benachrichtigen", style=discord.ButtonStyle.primary, emoji="🔔")
    async def notify_mod(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = datetime.datetime.utcnow()
        last = self.bot.get_cog("Support").cooldowns.get(interaction.user.id)

        if last and (now - last).total_seconds() < 1800:  # 30 Minuten Cooldown
            remaining = int(1800 - (now - last).total_seconds())
            await interaction.response.send_message(
                f"🕒 Bitte warte noch {remaining // 60} Minuten, bevor du erneut einen Mod benachrichtigst.",
                ephemeral=True)
        else:
            self.bot.get_cog("Support").cooldowns[interaction.user.id] = now
            await interaction.response.send_message("📣 Das Support-Team wurde benachrichtigt.", ephemeral=True)

            await interaction.channel.send(f"<@&1364923879138660363> – {interaction.user.mention} benötigt Hilfe.")

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Ticket wird geschlossen...", ephemeral=True)
        await interaction.channel.delete()

# ───── Musik ─────
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
FFMPEG_OPTIONS = {'options': '-vn'}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}

    def search_yt(self, url):
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {'source': info['url'], 'title': info['title']}
            except:
                return None

    async def play_next(self, ctx):
        if len(self.queue[ctx.guild.id]) > 0:
            url = self.queue[ctx.guild.id].pop(0)
            song = self.search_yt(url)
            if song:
                ctx.voice_client.play(discord.FFmpegPCMAudio(song['source'], **FFMPEG_OPTIONS),
                                      after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
                await ctx.send(f"🎶 Jetzt spielt: **{song['title']}**")

    @commands.command()
    async def join(self, ctx):
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            await ctx.send("✅ Beigetreten.")
        else:
            await ctx.send("❌ Du bist in keinem Sprachkanal.")

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Verlassen.")

    @commands.command()
    async def play(self, ctx, *, url):
        self.queue.setdefault(ctx.guild.id, [])
        if ctx.voice_client is None and ctx.author.voice:
            await ctx.author.voice.channel.connect()

        song = self.search_yt(url)
        if not song:
            await ctx.send("❌ Fehler beim Laden.")
            return

        if not ctx.voice_client.is_playing():
            ctx.voice_client.play(discord.FFmpegPCMAudio(song['source'], **FFMPEG_OPTIONS),
                                  after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            await ctx.send(f"🎶 Spielt: **{song['title']}**")
        else:
            self.queue[ctx.guild.id].append(url)
            await ctx.send(f"📥 Zur Warteschlange: **{song['title']}**")

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Übersprungen.")

    @commands.command()
    async def queue(self, ctx):
        q = self.queue.get(ctx.guild.id)
        if q:
            await ctx.send("📜 Warteschlange:\n" + "\n".join([f"{i+1}. {url}" for i, url in enumerate(q)]))
        else:
            await ctx.send("📭 Keine Lieder in der Warteschlange.")

#---- List Commands ---
async def post_all_commands(bot):
    channel = bot.get_channel(1364932182652616765)
    if not channel:
        print("❌ Der Commands-Channel wurde nicht gefunden.")
        return

    await channel.purge()

    prefix_commands = [
        f"🔹 `{bot.command_prefix}{cmd.name}` – {cmd.help or 'Keine Beschreibung'}"
        for cmd in bot.commands
        if not cmd.hidden
    ]

    slash_commands = await bot.tree.fetch_commands()
    slash_list = [
        f"🔸 `/{cmd.name}` – {cmd.description or 'Keine Beschreibung'}"
        for cmd in slash_commands
    ]

    embed = discord.Embed(
        title="📘 Alle Befehle des Bots",
        description="Hier findest du eine Übersicht aller verfügbaren Befehle.",
        color=discord.Color.blue()
    )

    if prefix_commands:
        embed.add_field(name="🛠️ Prefix-Befehle", value="\n".join(prefix_commands), inline=False)

    if slash_list:
        embed.add_field(name="⚙️ Slash-Befehle", value="\n".join(slash_list), inline=False)

    embed.set_footer(text="Letztes Update")
    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed)

# ───── Befehlsliste anzeigen ─────
async def post_all_commands(bot):
    channel = bot.get_channel(1364932182652616765)
    if not channel:
        print("❌ Der Commands-Channel wurde nicht gefunden.")
        return

    await channel.purge()

    # Prefix-Befehle sammeln
    prefix_commands = [
        f"🔹 `{bot.command_prefix}{cmd.name}` – {cmd.help or 'Keine Beschreibung'}"
        for cmd in bot.commands
        if not cmd.hidden
    ]

    # Slash-Befehle sammeln
    slash_commands = await bot.tree.fetch_commands()
    slash_list = [
        f"🔸 `/{cmd.name}` – {cmd.description or 'Keine Beschreibung'}"
        for cmd in slash_commands
    ]

    # Embed vorbereiten
    embed = discord.Embed(
        title="📘 Alle Befehle des Bots",
        description="Hier findest du eine Übersicht aller verfügbaren Befehle.",
        color=discord.Color.blue()
    )

    if prefix_commands:
        embed.add_field(name="🛠️ Prefix-Befehle", value="\n".join(prefix_commands), inline=False)
    if slash_list:
        embed.add_field(name="⚙️ Slash-Befehle", value="\n".join(slash_list), inline=False)

    embed.set_footer(text="Letztes Update")
    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == 1365036282291683419:
        guild = member.guild
        category = discord.utils.get(guild.categories, id=1365036730952061029)

        channel_name = f"{member.name}'s Raum"

        # TempVoice erstellen
        temp_channel = await guild.create_voice_channel(
            name=channel_name,
            category=category,
            user_limit=2,  # Start: User + 1
            reason="Temporärer Sprachkanal erstellt"
        )

        await member.move_to(temp_channel)

        async def update_user_limit():
            while True:
                await asyncio.sleep(5)

                if not guild.get_channel(temp_channel.id):
                    break

                if len(temp_channel.members) == 0:
                    await asyncio.sleep(60)
                    if len(temp_channel.members) == 0:
                        await temp_channel.delete(reason="Leerer Temp-Voice gelöscht")
                    break

                new_limit = len(temp_channel.members) + 1
                if temp_channel.user_limit != new_limit:
                    await temp_channel.edit(user_limit=new_limit)

        bot.loop.create_task(update_user_limit())


@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(1365038076648493086)
    if channel:
        await channel.send(f"🎉 Willkommen {member.mention} auf dem Server! 👋")
        try:
            await member.send(
                f"👋 Hey {member.name}, willkommen auf **{member.guild.name}**!"
                "\nSchön, dass du da bist! 😊"
                "\nSchau dir bitte die Regeln an und hab Spaß!"
            )
        except discord.Forbidden:
            print(f"⚠️ Konnte {member.name} keine DM senden.")


class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_messages = defaultdict(list)
        self.max_messages = 5
        self.time_frame = 1
        self.timeout_duration = 10
        self.EXEMPT_ROLE_IDS = [123456789012345678]
        self.LOG_CHANNEL_ID = 135791357913579135

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        member = message.author
        uid = member.id

        if any(role.id in self.EXEMPT_ROLE_IDS for role in member.roles):
            return

        now = time.time()
        self.user_messages[uid] = [t for t in self.user_messages[uid] if now - t < self.time_frame]
        self.user_messages[uid].append(now)

        if len(self.user_messages[uid]) > self.max_messages:
            try:
                deleted = []
                async for msg in message.channel.history(limit=100):
                    if msg.author == member and time.time() - msg.created_at.timestamp() < self.time_frame:
                        try:
                            await msg.delete()
                            deleted.append(msg)
                        except:
                            pass

                # Embed-Warnung
                warn_embed = discord.Embed(
                    title="🚫 Spam erkannt",
                    description=f"{member.mention}, du hast zu viele Nachrichten gesendet!",
                    color=discord.Color.red()
                )
                warn_embed.set_footer(text=f"Du wurdest für {self.timeout_duration} Sekunden gemutet.")
                await message.channel.send(embed=warn_embed, delete_after=5)

                # Timeout
                until = datetime.utcnow() + timedelta(seconds=self.timeout_duration)
                await member.edit(timeout_until=until)

                # Logging
                log_channel = self.bot.get_channel(self.LOG_CHANNEL_ID)
                if log_channel:
                    log_embed = discord.Embed(
                        title="📛 AntiSpam-Aktion",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    log_embed.add_field(name="Benutzer", value=f"{member} ({member.id})", inline=False)
                    log_embed.add_field(name="Grund", value="Spam erkannt", inline=False)
                    log_embed.add_field(name="Timeout", value=f"{self.timeout_duration} Sekunden", inline=True)
                    log_embed.add_field(name="Gelöschte Nachrichten", value=str(len(deleted)), inline=True)
                    await log_channel.send(embed=log_embed)

                print(f"[AntiSpam] {member} wurde getimeoutet & {len(deleted)} Nachrichten gelöscht.")

            except discord.Forbidden:
                print("[AntiSpam] Keine Berechtigung.")
            except Exception as e:
                print(f"[AntiSpam] Fehler: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def nuke(ctx):
    old_channel = ctx.channel
    try:
        # Kopiere Channel mit allen Einstellungen
        new_channel = await old_channel.clone(reason="Nuke verwendet")
        await new_channel.edit(position=old_channel.position)

        # Lösche alten Channel
        await old_channel.delete(reason="Nuke verwendet")

        # Sende Nuke-Bestätigung im neuen Channel
        await new_channel.send("💣 Dieser Channel wurde erfolgreich genuked!", delete_after=5)
        print(f"[NUKE] {ctx.author} hat #{old_channel.name} neu erstellt.")

    except discord.Forbidden:
        await ctx.send("🚫 Ich habe keine Berechtigung, diesen Channel zu löschen oder zu kopieren.")
    except Exception as e:
        await ctx.send(f"❌ Fehler beim Ausführen des Nuke-Befehls: `{e}`")




# ───── LOG ─────


async def log_message(channel_id: int, message: str):
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(message)


@bot.event
async def on_ready():
    print(f"Bot ist online als {bot.user}")


@bot.event
async def on_member_join(member):
    await log_message(1367623419847377007, f"📥 **{member}** ist dem Server beigetreten.")


@bot.event
async def on_member_remove(member):
    await log_message(1367623419847377007, f"📤 **{member}** hat den Server verlassen.")


@bot.event
async def on_user_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(f"Username geändert: `{before.name}` → `{after.name}`")
    if before.discriminator != after.discriminator:
        changes.append(f"Discriminator geändert: `{before.discriminator}` → `{after.discriminator}`")
    if before.avatar != after.avatar:
        changes.append("Avatar geändert")

    if changes:
        msg = f"🔄 **{before}** hat sein Profil geändert:\n" + "\n".join(changes)
        await log_message(1367623075687829634, msg)


@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        msg = f"📝 **{before}** hat seinen Nickname geändert: `{before.nick}` → `{after.nick}`"
        await log_message(1367623075687829634, msg)


@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    msg = (
        f"✏️ Nachricht bearbeitet von **{before.author}** in <#{before.channel.id}>:\n"
        f"**Vorher:** {before.content}\n**Nachher:** {after.content}"
    )
    await log_message(1367623531453612083, msg)


@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    msg = (
        f"🗑️ Nachricht von **{message.author}** in <#{message.channel.id}> gelöscht:\n"
        f"{message.content}"
    )
    await log_message(1367623531453612083, msg)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Du hast keine Berechtigung für diesen Befehl!")
        
# ───── Cogs hinzufügen und starten ─────
async def setup():
    await bot.add_cog(Moderation(bot))
    await bot.add_cog(General(bot))
    await bot.add_cog(Games(bot))
    await bot.add_cog(Levels(bot))
    await bot.add_cog(Support(bot))
    await bot.add_cog(Music(bot))
    await bot.add_cog(AntiSpam(bot))
    await bot.add_cog(SlashCommands(bot))

async def main():
    async with bot:
        await setup()
        await bot.start(TOKEN)

asyncio.run(main())

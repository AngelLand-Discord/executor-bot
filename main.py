import os
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# =====================
# CONFIG
# =====================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = 1023468164304097381
LOG_CHANNEL_ID = 1455212828947644579
PREFIX = "a "

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")

# =====================
# BOT SETUP
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# =====================
# DATABASE (FIXED)
# =====================
DB = sqlite3.connect(
    "bot.db",
    isolation_level=None,
    check_same_thread=False
)
DB.row_factory = sqlite3.Row
CUR = DB.cursor()

CUR.executescript("""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS judgements (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS tempbans (
    user_id INTEGER PRIMARY KEY,
    unban_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS modlogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target INTEGER NOT NULL,
    moderator INTEGER NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invites (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
""")

# =====================
# UTIL
# =====================
def now():
    return datetime.now(timezone.utc)

def log_db(action, target, moderator, reason=""):
    CUR.execute(
        """
        INSERT INTO modlogs (action, target, moderator, reason, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (action, target, moderator, reason, now().isoformat())
    )

async def log_embed(guild, embed):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

def clean_embed(title):
    return discord.Embed(
        title=title,
        color=discord.Color.dark_gray(),
        timestamp=now()
    )

# =====================
# OWNER LOCKS
# =====================
@bot.check
async def only_owner_prefix(ctx):
    return ctx.author.id == OWNER_ID

async def only_owner_slash(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        raise app_commands.CheckFailure
    return True

@bot.tree.error
async def slash_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You are not authorized to use this bot.",
            ephemeral=True
        )

# =====================
# TEMPBAN SCHEDULER
# =====================
async def schedule_unban(user_id, when):
    delay = (when - now()).total_seconds()
    if delay < 0:
        delay = 0

    await asyncio.sleep(delay)

    for guild in bot.guilds:
        try:
            await guild.unban(discord.Object(id=user_id))
        except:
            pass

    CUR.execute("DELETE FROM tempbans WHERE user_id=?", (user_id,))

# =====================
# READY
# =====================
@bot.event
async def on_ready():
    await bot.tree.sync()

    CUR.execute("SELECT user_id, unban_time FROM tempbans")
    for row in CUR.fetchall():
        asyncio.create_task(
            schedule_unban(
                row["user_id"],
                datetime.fromisoformat(row["unban_time"])
            )
        )

    print(f"Online as {bot.user}")

# =====================
# CORE LOGIC
# =====================
async def judgement_core(guild, moderator, member, reason):
    roles = [r for r in member.roles if r != guild.default_role]
    if not roles:
        return False, "User has no roles."

    for r in roles:
        CUR.execute(
            "INSERT OR IGNORE INTO judgements VALUES (?,?)",
            (member.id, r.id)
        )

    await member.remove_roles(*roles, reason=reason)
    log_db("judgement", member.id, moderator.id, reason)

    embed = clean_embed("JUDGEMENT EXECUTED")
    embed.add_field(name="Target", value=member, inline=False)
    embed.add_field(name="Moderator", value=moderator, inline=False)
    embed.add_field(name="Roles Removed", value=len(roles), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)

    await log_embed(guild, embed)
    return True, None

# =====================
# PREFIX COMMANDS
# =====================
@bot.command()
async def judgement(ctx, member: discord.Member, *, reason="Judgement passed"):
    ok, err = await judgement_core(ctx.guild, ctx.author, member, reason)
    await ctx.send(err if not ok else f"⚖️ {member.mention} judged.")

@bot.command()
async def restore(ctx, member: discord.Member):
    CUR.execute("SELECT role_id FROM judgements WHERE user_id=?", (member.id,))
    rows = CUR.fetchall()
    if not rows:
        await ctx.send("Nothing to restore.")
        return

    roles = [ctx.guild.get_role(r["role_id"]) for r in rows if ctx.guild.get_role(r["role_id"])]
    await member.add_roles(*roles)

    CUR.execute("DELETE FROM judgements WHERE user_id=?", (member.id,))
    log_db("restore", member.id, ctx.author.id)

    embed = clean_embed("ROLES RESTORED")
    embed.add_field(name="Target", value=member)
    embed.add_field(name="Moderator", value=ctx.author)
    await log_embed(ctx.guild, embed)

    await ctx.send(f"♻️ Roles restored for {member.mention}")

@bot.command()
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="Muted"):
    until = now() + timedelta(minutes=minutes)
    await member.timeout(until, reason=reason)
    log_db("mute", member.id, ctx.author.id, reason)

    embed = clean_embed("USER MUTED")
    embed.add_field(name="User", value=member)
    embed.add_field(name="Duration", value=f"{minutes} minutes")
    await log_embed(ctx.guild, embed)

    await ctx.send(f"🔇 {member.mention} muted.")

@bot.command()
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    log_db("unmute", member.id, ctx.author.id)

    embed = clean_embed("USER UNMUTED")
    embed.add_field(name="User", value=member)
    await log_embed(ctx.guild, embed)

    await ctx.send(f"🔊 {member.mention} unmuted.")

@bot.command()
async def ban(ctx, member: discord.Member, *, reason="Banned"):
    await member.ban(reason=reason)
    log_db("ban", member.id, ctx.author.id, reason)

    embed = clean_embed("USER BANNED")
    embed.add_field(name="User", value=member)
    embed.add_field(name="Reason", value=reason)
    await log_embed(ctx.guild, embed)

    await ctx.send(f"🚫 {member} banned.")

@bot.command()
async def tempban(ctx, member: discord.Member, minutes: int, *, reason="Tempban"):
    until = now() + timedelta(minutes=minutes)
    await member.ban(reason=reason)

    CUR.execute(
        "INSERT OR REPLACE INTO tempbans VALUES (?,?)",
        (member.id, until.isoformat())
    )

    asyncio.create_task(schedule_unban(member.id, until))
    log_db("tempban", member.id, ctx.author.id, reason)

    embed = clean_embed("USER TEMPBANNED")
    embed.add_field(name="User", value=member)
    embed.add_field(name="Duration", value=f"{minutes} minutes")
    await log_embed(ctx.guild, embed)

    await ctx.send(f"⏳ {member} tempbanned.")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    CUR.execute("""
        SELECT action, COUNT(*) c
        FROM modlogs
        WHERE target=?
        GROUP BY action
    """, (member.id,))
    history = "\n".join(f"{r['action']}: {r['c']}" for r in CUR.fetchall()) or "Clean record"

    CUR.execute(
        "SELECT count FROM invites WHERE guild_id=? AND user_id=?",
        (ctx.guild.id, member.id)
    )
    row = CUR.fetchone()
    invites = row["count"] if row else 0

    embed = clean_embed("USER INFO")
    embed.add_field(name="User", value=member, inline=False)
    embed.add_field(name="Invites", value=invites, inline=False)
    embed.add_field(name="Mod History", value=history, inline=False)

    await ctx.send(embed=embed)

# =====================
# SLASH COMMANDS
# =====================
@bot.tree.command(name="judgement", description="Remove all roles from a member")
@app_commands.check(only_owner_slash)
async def slash_judgement(interaction, member: discord.Member, reason: str = "Judgement passed"):
    ok, err = await judgement_core(interaction.guild, interaction.user, member, reason)
    await interaction.response.send_message(
        err if not ok else "Judgement executed.",
        ephemeral=True
    )

@slash_judgement.autocomplete("reason")
async def judgement_reason_auto(_, current):
    reasons = ["Rule violation", "Abuse", "Spam", "Harassment", "Staff decision"]
    return [
        app_commands.Choice(name=r, value=r)
        for r in reasons
        if current.lower() in r.lower()
    ]

# =====================
# INVITE TRACKING
# =====================
@bot.event
async def on_member_join(member):
    CUR.execute("""
        INSERT INTO invites (guild_id, user_id, count)
        VALUES (?, ?, 1)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET count = count + 1
    """, (member.guild.id, member.id))

# =====================
# RUN
# =====================
bot.run(TOKEN)

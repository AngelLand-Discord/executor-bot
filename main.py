import discord
from discord.ext import commands
import os

# =========================
# ENV VARIABLES
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

PREFIX = "!"

if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables.")

if not OWNER_ID:
    raise ValueError("OWNER_ID not found in environment variables.")

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Store active DM sessions
active_dm_sessions = {}

# =========================
# READY EVENT
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Owner-only mode enabled.")

# =========================
# OWNER CHECK
# =========================
@bot.check
async def only_owner(ctx):
    return ctx.author.id == OWNER_ID

# =========================
# DM COMMAND
# =========================
@bot.command(name="dm")
async def dm(ctx, member: discord.Member, *, message: str):
    try:
        await member.send(message)
        active_dm_sessions[member.id] = ctx.channel.id
        await ctx.send(f"DM sent to {member.mention} ✅")
    except Exception as e:
        await ctx.send(f"Failed to send DM: {e}")

# =========================
# DM RELAY
# =========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        if message.author.id in active_dm_sessions:
            channel_id = active_dm_sessions[message.author.id]
            channel = bot.get_channel(channel_id)

            if channel:
                await channel.send(
                    f"📩 Reply from **{message.author.name}**:\n{message.content}"
                )

    await bot.process_commands(message)

# =========================
# RUN
# =========================
bot.run(TOKEN)

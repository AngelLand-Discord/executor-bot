import discord
from discord.ext import commands
import asyncio
import os
import threading
from flask import Flask

# =========================
# ENV VARIABLES
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
PORT = int(os.getenv("PORT", 10000))

# channel where ALL bot DMs get logged
DM_LOG_CHANNEL = int(os.getenv("DM_LOG_CHANNEL"))

PREFIX = "tm "

# =========================
# DISCORD INTENTS
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# store DM relay sessions
active_dm_sessions = {}

# =========================
# FLASK SERVER (RENDER PORT)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive."

def run_web():
    app.run(host="0.0.0.0", port=PORT)

# =========================
# READY EVENT
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot + Web server running.")

# =========================
# OWNER CHECK
# =========================
@bot.check
async def only_owner(ctx):
    return ctx.author.id == OWNER_ID

# =========================
# DM COMMAND
# =========================
@bot.command()
async def dm(ctx, member: discord.Member, *, message: str):

    try:
        await member.send(message)

        # store relay session
        active_dm_sessions[member.id] = ctx.channel.id

        await ctx.send(f"DM sent to {member.mention}")

    except Exception as e:
        await ctx.send(f"Failed to send DM: {e}")

# =========================
# ROLE ANNOUNCEMENT
# =========================
@bot.command()
async def announce(ctx, role: discord.Role, *, message: str):

    success = 0
    failed = 0

    await ctx.send(f"Sending announcement to {role.name}...")

    for member in role.members:

        if member.bot:
            continue

        try:
            await member.send(message)
            success += 1
            await asyncio.sleep(0.5)

        except:
            failed += 1

    await ctx.send(
        f"Announcement complete\n"
        f"Sent: {success}\n"
        f"Failed (DM closed): {failed}"
    )

# =========================
# MESSAGE HANDLER
# =========================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # =========================
    # HANDLE DMs
    # =========================
    if isinstance(message.channel, discord.DMChannel):

        log_channel = bot.get_channel(DM_LOG_CHANNEL)

        # relay replies to original channel
        if message.author.id in active_dm_sessions:

            relay_channel_id = active_dm_sessions[message.author.id]
            relay_channel = bot.get_channel(relay_channel_id)

            if relay_channel:
                await relay_channel.send(
                    f"Reply from {message.author.name}:\n{message.content}"
                )

        # log all DMs
        if log_channel:
            await log_channel.send(
                f"DM received\n"
                f"User: {message.author} ({message.author.id})\n"
                f"Message: {message.content}"
            )

    await bot.process_commands(message)

# =========================
# START BOTH SERVICES
# =========================
if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    bot.run(TOKEN)

import discord
from discord.ext import commands
import os
import threading
from flask import Flask

# =========================
# ENV VARIABLES
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
PORT = int(os.getenv("PORT", 10000))

PREFIX = "tm "

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

active_dm_sessions = {}

# =========================
# FLASK SERVER (FOR RENDER)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive."

def run_web():
    app.run(host="0.0.0.0", port=PORT)

# =========================
# BOT EVENTS
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Web + Bot running.")

@bot.check
async def only_owner(ctx):
    return ctx.author.id == OWNER_ID

@bot.command(name="dm")
async def dm(ctx, member: discord.Member, *, message: str):
    await member.send(message)
    active_dm_sessions[member.id] = ctx.channel.id
    await ctx.send("DM sent.")

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
                    f"📩 Reply from {message.author.name}:\n{message.content}"
                )

    await bot.process_commands(message)

# =========================
# START BOTH
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)


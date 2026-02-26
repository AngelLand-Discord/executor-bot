import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

YDL_OPTIONS = {
    "format": "bestaudio",
    "noplaylist": True,
    "default_search": "ytsearch"
}

FFMPEG_OPTIONS = {
    "options": "-vn"
}

queues = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

async def get_audio_source(query):
    loop = asyncio.get_event_loop()

    def extract():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            return info

    info = await loop.run_in_executor(None, extract)

    if "entries" in info:
        info = info["entries"][0]

    return info["url"], info["title"]

async def play_next(ctx):
    queue = get_queue(ctx.guild.id)

    if not queue:
        return

    url = queue.pop(0)
    source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)

    ctx.voice_client.play(
        source,
        after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
    )

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command()
async def play(ctx, *, query):
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    url, title = await get_audio_source(query)
    queue = get_queue(ctx.guild.id)

    if ctx.voice_client.is_playing():
        queue.append(url)
        await ctx.send(f"Queued: {title}")
    else:
        source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )
        await ctx.send(f"Now playing: {title}")

bot.run(TOKEN)

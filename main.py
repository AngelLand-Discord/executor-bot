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
DM_LOG_CHANNEL = int(os.getenv("DM_LOG_CHANNEL"))

PREFIX = "tm "

# =========================
# INTENTS
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

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
# READY
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot running.")

# =========================
# OWNER ONLY COMMANDS
# =========================
@bot.check
async def only_owner(ctx):
    return ctx.author.id == OWNER_ID

# =========================
# DM USER
# =========================
@bot.command()
async def dm(ctx, member: discord.Member, *, message: str):

    try:
        await member.send(message)
        await ctx.send(f"DM sent to {member.mention}")

    except Exception as e:
        await ctx.send(f"Failed: {e}")

# =========================
# ANNOUNCE TO ROLE
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
        f"Failed: {failed}"
    )

# =========================
# SEND MESSAGE TO CHANNEL
# =========================
@bot.command()
async def msg(ctx, channel: discord.TextChannel, *, message: str):

    try:
        await channel.send(message)
        await ctx.send(f"Message sent to {channel.mention}")

    except Exception as e:
        await ctx.send(f"Failed to send: {e}")

# =========================
# LOCK CHANNEL
# =========================
@bot.command()
async def lock(ctx, channel: discord.TextChannel):

    try:
        everyone = ctx.guild.default_role

        await channel.set_permissions(
            everyone,
            view_channel=False
        )

        await ctx.send(f"{channel.mention} locked.")

    except Exception as e:
        await ctx.send(f"Failed to lock: {e}")

# =========================
# UNLOCK CHANNEL
# =========================
@bot.command()
async def unlock(ctx, channel: discord.TextChannel):

    try:
        everyone = ctx.guild.default_role

        await channel.set_permissions(
            everyone,
            view_channel=True
        )

        await ctx.send(f"{channel.mention} unlocked.")

    except Exception as e:
        await ctx.send(f"Failed to unlock: {e}")

# =========================
# LOG ALL BOT DMs
# =========================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):

        log_channel = bot.get_channel(DM_LOG_CHANNEL)

        if log_channel:
            await log_channel.send(
                f"DM received\n"
                f"User: {message.author} ({message.author.id})\n"
                f"Message: {message.content}"
            )

    await bot.process_commands(message)

@bot.command()
async def removeperm(ctx, member: discord.Member, permission: str):

    guild = ctx.guild
    role_name = f"deny_{permission}"

    try:
        # Check if role already exists
        role = discord.utils.get(guild.roles, name=role_name)

        if role is None:
            perms = discord.Permissions.none()

            # create role with the permission disabled
            role = await guild.create_role(
                name=role_name,
                permissions=perms,
                reason="Permission override role"
            )

        # apply channel overrides
        for channel in guild.channels:
            try:
                overwrite = channel.overwrites_for(role)
                setattr(overwrite, permission, False)
                await channel.set_permissions(role, overwrite=overwrite)
            except:
                pass

        await member.add_roles(role)

        await ctx.send(
            f"{member.mention} can no longer use **{permission}** anywhere."
        )

    except Exception as e:
        await ctx.send(f"Failed: {e}")

@bot.command()
async def restoreperm(ctx, member: discord.Member, permission: str):

    guild = ctx.guild
    role_name = f"deny_{permission}"

    role = discord.utils.get(guild.roles, name=role_name)

    if role is None:
        await ctx.send("No override role found.")
        return

    try:
        # remove role from member
        if role in member.roles:
            await member.remove_roles(role)

        # remove channel overrides
        for channel in guild.channels:
            try:
                overwrite = channel.overwrites_for(role)
                setattr(overwrite, permission, None)
                await channel.set_permissions(role, overwrite=overwrite)
            except:
                pass

        # delete role if nobody has it anymore
        if len(role.members) == 0:
            await role.delete()

        await ctx.send(
            f"{member.mention} can use **{permission}** again."
        )

    except Exception as e:
        await ctx.send(f"Failed to restore permission: {e}")

# =========================
# GIVE PERMISSION TO ROLE
# =========================
@bot.command()
async def giveperm(ctx, role: discord.Role, permission: str):

    perms = role.permissions

    if not hasattr(perms, permission):
        await ctx.send("Invalid permission name.")
        return

    try:
        setattr(perms, permission, True)
        await role.edit(permissions=perms)

        await ctx.send(
            f"{role.mention} now has **{permission}** permission."
        )

    except Exception as e:
        await ctx.send(f"Failed: {e}")


# =========================
# REMOVE PERMISSION FROM ROLE
# =========================
@bot.command()
async def remroleperm(ctx, role: discord.Role, permission: str):

    perms = role.permissions

    if not hasattr(perms, permission):
        await ctx.send("Invalid permission name.")
        return

    try:
        setattr(perms, permission, False)
        await role.edit(permissions=perms)

        await ctx.send(
            f"Removed **{permission}** from {role.mention}."
        )

    except Exception as e:
        await ctx.send(f"Failed: {e}")


# =========================
# REMOVE PERMISSION FROM ALL ROLES
# =========================
@bot.command()
async def remallperm(ctx, permission: str):

    guild = ctx.guild
    updated = 0

    for role in guild.roles:

        if role.is_default():
            continue

        perms = role.permissions

        if not hasattr(perms, permission):
            continue

        if getattr(perms, permission):

            try:
                setattr(perms, permission, False)
                await role.edit(permissions=perms)
                updated += 1
            except:
                pass

    await ctx.send(
        f"Removed **{permission}** from {updated} roles."
    )

# =========================
# START SERVICES
# =========================
if __name__ == "__main__":

    threading.Thread(target=run_web).start()
    print("Starting Discord bot...")
    print("Token loaded:", TOKEN is not None)
    bot.run(TOKEN)






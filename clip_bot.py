"""
Discord bot with two commands (NSFW channels only):
    /tits   -> 5-10 clips up to 20 seconds
    /tits2  -> 5-10 clips up to 60 seconds
Only clips tagged "big tits" or "big boobs" on Redgifs are used.
"""
import asyncio
import io
import os
import random

import aiohttp
import discord
from discord import app_commands

API = "https://api.redgifs.com/v2"
SEARCH_TERMS = ["big tits", "big boobs"]
ALLOWED_TAGS = {"big tits", "big boobs"}
HEADERS = {"User-Agent": "Mozilla/5.0 (clip-bot)"}

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

_token = {"value": None}
_seen: set[str] = set()


async def get_token(session, refresh=False) -> str:
    if _token["value"] and not refresh:
        return _token["value"]
    async with session.get(f"{API}/auth/temporary", headers=HEADERS) as r:
        r.raise_for_status()
        _token["value"] = (await r.json())["token"]
    return _token["value"]


async def fetch_page(session, term: str, page: int) -> list[dict]:
    params = {
        "search_text": term,
        "order": random.choice(["trending", "top7", "latest"]),
        "count": 80,
        "page": page,
    }
    for attempt in range(2):
        token = await get_token(session, refresh=attempt == 1)
        headers = {**HEADERS, "Authorization": f"Bearer {token}"}
        async with session.get(f"{API}/gifs/search", params=params, headers=headers) as r:
            if r.status == 401:
                continue
            r.raise_for_status()
            return (await r.json()).get("gifs", [])
    return []


def is_match(gif: dict, max_seconds: int) -> bool:
    tags = {t.lower() for t in gif.get("tags", [])}
    return (
        gif.get("id") not in _seen
        and bool(tags & ALLOWED_TAGS)
        and (gif.get("duration") or 999) <= max_seconds
        and bool(gif.get("urls", {}).get("sd"))
    )


async def find_clips(session, max_seconds: int, want: int) -> list[dict]:
    found: dict[str, dict] = {}
    for _ in range(4):
        term = random.choice(SEARCH_TERMS)
        for gif in await fetch_page(session, term, random.randint(1, 6)):
            if is_match(gif, max_seconds):
                found[gif["id"]] = gif
        if len(found) >= want * 3:
            break
    clips = list(found.values())
    random.shuffle(clips)
    return clips


async def download(session, url: str, limit: int) -> bytes | None:
    async with session.get(url, headers=HEADERS) as r:
        if r.status != 200:
            return None
        if int(r.headers.get("Content-Length", 0)) > limit:
            return None
        data = await r.read()
        return data if len(data) <= limit else None


async def run(interaction: discord.Interaction, count: int, max_seconds: int):
    channel = interaction.channel
    if not getattr(channel, "is_nsfw", lambda: False)():
        await interaction.response.send_message(
            "This command only works in age-restricted (NSFW) channels.", ephemeral=True
        )
        return

    await interaction.response.defer()
    limit = interaction.guild.filesize_limit if interaction.guild else 10 * 1024 * 1024
    sent = 0

    async with aiohttp.ClientSession() as session:
        for gif in await find_clips(session, max_seconds, count):
            if sent >= count:
                break
            data = await download(session, gif["urls"]["sd"], limit)
            if not data:
                continue
            _seen.add(gif["id"])
            await interaction.followup.send(
                file=discord.File(io.BytesIO(data), filename=f"{gif['id']}.mp4")
            )
            sent += 1
            await asyncio.sleep(1)

    if sent == 0:
        await interaction.followup.send("Couldn't find any matching clips right now, try again.")
    elif sent < count:
        await interaction.followup.send(f"Only found {sent} matching clips that fit the size limit.")


@tree.command(name="tits", description="Post clips up to 20 seconds (NSFW channels only)")
@app_commands.describe(count="How many clips (5-10)")
async def tits(interaction: discord.Interaction, count: app_commands.Range[int, 5, 10] = 5):
    await run(interaction, count, max_seconds=20)


@tree.command(name="tits2", description="Post clips up to 1 minute (NSFW channels only)")
@app_commands.describe(count="How many clips (5-10)")
async def tits2(interaction: discord.Interaction, count: app_commands.Range[int, 5, 10] = 5):
    await run(interaction, count, max_seconds=60)


@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")


token = os.environ.get("DISCORD_TOKEN")
if not token:
    with open("token.txt") as f:
        token = f.read().strip()
bot.run(token)

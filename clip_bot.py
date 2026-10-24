"""
Discord bot with two commands (NSFW channels only):
    /tits   -> 5-10 clips up to 20 seconds
    /tits2  -> 5-10 clips up to 60 seconds
Only clips tagged "big tits" or "big boobs" on Redgifs are used.

Setup:
    pip install -U discord.py aiohttp
    export DISCORD_TOKEN="your-bot-token"
    python clip_bot.py
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
ALLOWED_TAGS = {"big tits", "big boobs"}  # a clip must carry at least one of these
HEADERS = {"User-Agent": "Mozilla/5.0 (clip-bot)"}

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

_token = {"value": None}
_seen: set[str] = set()  # avoid reposting the same clip


async def get_token(session, refresh=False) -> str:
    if _token["value"] and not refresh:
        return _token["value"]

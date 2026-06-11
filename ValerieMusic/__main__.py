import asyncio
import importlib
import os

import aiohttp
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from ValerieMusic import LOGGER, app, userbot
from ValerieMusic.core.call import Valerie
from ValerieMusic.core.mongo import sync_backup
from ValerieMusic.misc import sudo
from ValerieMusic.plugins import ALL_MODULES
from ValerieMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


def _looks_like_cookies(content: str) -> bool:
    """
    A valid Netscape cookies file either starts with the header comment
    or has tab-separated lines with at least 7 fields (domain ... value).
    Reject anything that looks like HTML or is empty.
    """
    if not content:
        return False
    stripped = content.strip()
    if stripped.startswith("<"):
        return False
    # Allow the standard header
    if stripped.startswith("# Netscape HTTP Cookie File"):
        return True
    # Check first non-comment line for tab-separated cookie fields
    for line in stripped.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        return "\t" in line and len(line.split("\t")) >= 7
    return False


def _to_raw_url(url: str) -> str:
    """
    Convert a pastebin-style view URL to its raw-text equivalent.
    Works for batbin.me, hastebin, pastebin.com, etc.

    batbin.me/abc       → batbin.me/raw/abc
    hastebin.com/abc    → hastebin.com/raw/abc
    pastebin.com/abc    → pastebin.com/raw/abc
    already /raw/...    → unchanged
    """
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path.startswith("raw/"):
        return url  # already raw
    # Insert 'raw' before the last path segment (the paste ID)
    parts = path.split("/")
    parts.insert(max(len(parts) - 1, 0), "raw")
    raw_path = "/" + "/".join(parts)
    return urlunparse(parsed._replace(path=raw_path))


async def download_cookies():
    """
    Download fresh cookies from COOKIES_URL at startup.
    Handles pastebin-style sites that serve HTML on the view URL —
    automatically retries with the /raw/ endpoint in that case.
    """
    if not config.COOKIES_URLS:
        return

    cookies_path = os.path.join(os.getcwd(), "cookies.txt")
    original_url = config.COOKIES_URLS[0]

    async def fetch(url: str) -> str | None:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception as e:
            LOGGER("ValerieMusic").warning(f"Cookies fetch error ({url}): {e}")
        return None

    content = await fetch(original_url)

    if not _looks_like_cookies(content):
        raw_url = _to_raw_url(original_url)
        if raw_url != original_url:
            LOGGER("ValerieMusic").info(
                f"Cookies URL returned HTML, retrying raw endpoint: {raw_url}"
            )
            content = await fetch(raw_url)

    if _looks_like_cookies(content):
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(content)
        LOGGER("ValerieMusic").info(f"Cookies written successfully to {cookies_path}")
    else:
        LOGGER("ValerieMusic").warning(
            "Downloaded content is not a valid Netscape cookies file — "
            "skipping write. Bot will use existing cookies.txt if present."
        )


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()

    await sudo()

    # Seed the MySQL local backup from MongoDB (no-op unless both are set).
    try:
        await sync_backup()
    except Exception:
        pass

    # Download fresh cookies before starting so yt-dlp search works properly
    await download_cookies()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)

        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception:
        pass

    await app.start()

    for all_module in ALL_MODULES:
        importlib.import_module("ValerieMusic.plugins" + all_module)

    LOGGER("ValerieMusic.plugins").info("Successfully Imported Modules...")

    await userbot.start()
    await Valerie.start()

    try:
        await Valerie.stream_call(
            "https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4"
        )
    except NoActiveGroupCall:
        LOGGER("ValerieMusic").error(
            "Please turn on the videochat of your log group/channel.\n\nStopping Bot..."
        )
        exit()
    except Exception:
        pass

    await Valerie.decorators()

    LOGGER("ValerieMusic").info(
        "\x52\x6f\x63\x6b\x73\x20\x4d\x75\x73\x69\x63\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e"
        "\x0a\x0a"
        "\x44\x6f\x6e\x27\x74\x20\x66\x6f\x72\x67\x65\x74\x20\x74\x6f\x20\x76\x69\x73\x69\x74\x20\x40\x53\x41\x48\x58\x59\x5a\x38\x38"
    )

    await idle()

    await app.stop()
    await userbot.stop()

    LOGGER("ValerieMusic").info("Stopping Valerie Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())

import random
import string
from urllib.parse import quote_plus

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ValerieMusic import app
from config import BANNED_USERS, SONG_PLAYER_URL

# ── In-memory query store ─────────────────────────────────────
# Telegram enforces a 64-byte limit on callback_data, so we can't
# embed the full song query there. We store it in a dict keyed by a
# short random token and pass only the token in the callback.
_song_cache: dict = {}


def _store(query: str) -> str:
    """Save query, return an 8-char token."""
    key = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    _song_cache[key] = query
    return key


# ── /song command ─────────────────────────────────────────────
@app.on_message(
    filters.command(
        ["song"],
        prefixes=["/", "!", ".", "@", ",", ""],
    )
    & ~BANNED_USERS
)
async def song_command(client, message: Message):
    # FIX: with empty-prefix support this can fire on captions where
    # message.text is None → AttributeError on .split(). Safe text source.
    text = message.text or message.caption or ""
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ **Usage:** `/song <song name or YouTube URL>`\n\n"
            "**Example:** `/song Blinding Lights`",
            disable_web_page_preview=True,
        )

    query = text.split(None, 1)[1].strip()
    key   = _store(query)

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎧 Audio", callback_data=f"SongDL a|{key}"),
                InlineKeyboardButton("🎬 Video", callback_data=f"SongDL v|{key}"),
            ]
        ]
    )

    await message.reply_text(
        f"🎵 **{query}**\n\n"
        "Choose your preferred download format:",
        reply_markup=buttons,
    )


# ── Format-choice callback ─────────────────────────────────────
@app.on_callback_query(filters.regex(r"^SongDL ") & ~BANNED_USERS)
async def song_download_cb(client, callback_query: CallbackQuery):
    # Parse payload: "SongDL <mode_code>|<key>"
    try:
        payload              = callback_query.data.split(" ", 1)[1]
        mode_code, cache_key = payload.split("|", 1)
    except (IndexError, ValueError):
        return await callback_query.answer("Invalid request.", show_alert=True)

    query = _song_cache.get(cache_key)
    if not query:
        return await callback_query.answer(
            "⚠️ Session expired — please send /song again.",
            show_alert=True,
        )

    mode       = "audio" if mode_code == "a" else "video"
    mode_label = "🎧 Audio" if mode == "audio" else "🎬 Video"

    # Build deep-link URL into the RocksPlayer website
    # The player reads ?q= and ?mode= on load and auto-searches
    player_url = f"{SONG_PLAYER_URL}?q={quote_plus(query)}&mode={mode}"

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬇️ Download Song", url=player_url)
            ]
        ]
    )

    await callback_query.message.edit_text(
        f"🎵 **{query}**\n"
        f"📌 Format: {mode_label}\n\n"
        "⚠️ Telegram does not allow songs to be downloaded here.\n\n"
        "Download the song from here 👇",
        reply_markup=buttons,
        disable_web_page_preview=True,
    )
    await callback_query.answer()

"""
scangroups.py  —  ValerieMusic sudo plugin

Scans every group/supergroup/channel the assistants (userbots) are in,
verifies each with the bot account, and saves full metadata to MySQL.

Why assistants and not the bot?
  Telegram bots cannot call messages.GetDialogs (BOT_METHOD_INVALID).
  The userbot assistant accounts CAN enumerate their dialogs.

Root cause of "broadcast only hit N chats":
  chatsdb only gets a new entry when someone runs /start in that group.
  Any group the bot was added to silently (without /start) is invisible
  to /broadcast. Run /scangroups once to populate chatsdb from the
  assistants' actual dialog lists, then /broadcast will reach everyone.

Usage (sudo only):
    /scangroups        — full scan with live progress
    /scangroups stats  — show DB counts without scanning
"""

import asyncio
import logging

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import (
    ChannelPrivate,
    ChatAdminRequired,
    ChatWriteForbidden,
    FloodWait,
    PeerIdInvalid,
    UserNotParticipant,
)
from pyrogram.types import Message

from ValerieMusic import app
from ValerieMusic.misc import SUDOERS
from ValerieMusic.core.mongo import mongodb
from ValerieMusic.utils.database import (
    add_served_chat,
    get_served_chats,
    get_client,
)

_LOG = logging.getLogger(__name__)

# Full-metadata collection (separate from chatsdb so we don't interfere
# with the existing served-chats logic used by /broadcast and autoend)
groupsdb = mongodb.scanned_groups

# Direct reference to chatsdb for pruning stale entries
# (ValerieMusic doesn't expose delete_served_chat, so we write directly)
_chatsdb = mongodb.chats

_VALID_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}
_INACCESSIBLE = (ChannelPrivate, PeerIdInvalid, UserNotParticipant, ChatAdminRequired)


# ── DB helpers ───────────────────────────────────────────────────────────────

async def upsert_scanned_group(data: dict):
    await groupsdb.update_one(
        {"chat_id": data["chat_id"]}, {"$set": data}, upsert=True
    )

async def remove_scanned_group(chat_id: int):
    await groupsdb.delete_one({"chat_id": chat_id})

async def _delete_served_chat(chat_id: int):
    """Remove a chat from chatsdb (pruning stale entries)."""
    await _chatsdb.delete_one({"chat_id": chat_id})

async def count_scanned_groups() -> int:
    return await groupsdb.count_documents({"chat_id": {"$lt": 0}})


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_chat_safe(chat_id: int):
    """Fetch Chat via the bot account; return None if inaccessible."""
    try:
        return await app.get_chat(chat_id)
    except FloodWait as fw:
        await asyncio.sleep(fw.value + 2)
        try:
            return await app.get_chat(chat_id)
        except Exception:
            return None
    except _INACCESSIBLE:
        return None
    except Exception as exc:
        _LOG.debug(f"get_chat({chat_id}) skipped: {exc}")
        return None


def _build_metadata(chat) -> dict:
    return {
        "chat_id":       chat.id,
        "title":         chat.title or "Unknown",
        "username":      f"@{chat.username}" if chat.username else None,
        "type":          str(chat.type).split(".")[-1].lower(),
        "members":       getattr(chat, "members_count", None),
        "description":   getattr(chat, "description", None),
        "invite_link":   getattr(chat, "invite_link", None),
        "is_verified":   getattr(chat, "is_verified", False),
        "is_restricted": getattr(chat, "is_restricted", False),
        "accessible":    True,
    }


async def _edit_safe(msg: Message, text: str):
    try:
        await msg.edit_text(text)
    except Exception:
        pass


# ── Core scanner ─────────────────────────────────────────────────────────────

async def scan_all_groups(progress_msg: Message = None) -> dict:
    from ValerieMusic.core.userbot import assistants

    # Phase 1: collect chat IDs from all active assistant userbots
    await _edit_safe(progress_msg, "🔍 **Phase 1/3 — Discovering groups via assistants…**")

    found: set = set()

    for num in assistants:
        client = await get_client(num)
        if client is None:
            continue
        assistant_count = 0
        try:
            async for dialog in client.get_dialogs():
                try:
                    chat = dialog.chat
                    if chat.type not in _VALID_TYPES:
                        continue
                    found.add(chat.id)
                    assistant_count += 1
                    if assistant_count % 100 == 0:
                        await asyncio.sleep(1)
                        await _edit_safe(
                            progress_msg,
                            f"🔍 **Phase 1/3** — Assistant {num}: "
                            f"`{assistant_count}` groups…\nTotal unique: `{len(found)}`",
                        )
                except Exception:
                    continue
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 2)
        except Exception as exc:
            _LOG.warning(f"Assistant {num} get_dialogs failed: {exc}")

    # Also keep everything already in chatsdb so we don't lose existing entries
    for rec in await get_served_chats():
        found.add(int(rec["chat_id"]))

    await _edit_safe(
        progress_msg,
        f"✅ **Phase 1 done** — `{len(found)}` unique groups found.\n\n"
        f"📥 **Phase 2/3 — Verifying & saving metadata…**",
    )

    # Phase 2: verify via bot account + upsert to DB
    found_list = list(found)
    accessible: set = set()
    added_new = updated = errors = 0

    for idx, chat_id in enumerate(found_list, 1):
        chat = await _get_chat_safe(chat_id)
        if chat is None:
            errors += 1
            continue

        accessible.add(chat_id)
        meta = _build_metadata(chat)
        existing = await groupsdb.find_one({"chat_id": chat_id})
        await upsert_scanned_group(meta)
        await add_served_chat(chat_id)   # populates chatsdb → /broadcast now reaches it

        if existing:
            updated += 1
        else:
            added_new += 1

        if progress_msg and idx % 30 == 0:
            await _edit_safe(
                progress_msg,
                f"📥 **Phase 2/3** — `{idx}/{len(found_list)}`\n"
                f"➕ New: `{added_new}` | 🔄 Updated: `{updated}` | ⚠️ Errors: `{errors}`",
            )
        await asyncio.sleep(0.05)

    # Phase 3: prune stale chatsdb entries the bot can no longer access
    await _edit_safe(progress_msg, "🧹 **Phase 3/3 — Pruning stale entries…**")

    pruned = 0
    for rec in await get_served_chats():
        db_chat_id = int(rec["chat_id"])
        if db_chat_id in accessible:
            continue
        await _delete_served_chat(db_chat_id)
        await remove_scanned_group(db_chat_id)
        pruned += 1
        await asyncio.sleep(0.05)

    return {
        "total_found": len(found),
        "accessible":  len(accessible),
        "added_new":   added_new,
        "updated":     updated,
        "pruned":      pruned,
        "errors":      errors,
    }


# ── Command handler ──────────────────────────────────────────────────────────

@app.on_message(filters.command(["scangroups", "scanchats"]) & SUDOERS)
async def scangroups_command(client, message: Message):
    args = message.text.split()[1:]

    if args and args[0].lower() == "stats":
        served  = len(await get_served_chats())
        scanned = await count_scanned_groups()
        return await message.reply_text(
            f"📊 **Group Database Stats**\n\n"
            f"• Served chats (chatsdb):     `{served}`\n"
            f"• Scanned groups (full meta): `{scanned}`\n\n"
            f"Run /scangroups to refresh."
        )

    progress = await message.reply_text(
        "⚙️ **Starting group scan…**\n"
        "Walking all assistant dialogs to discover every group the bot is in."
    )

    try:
        result = await scan_all_groups(progress_msg=progress)
    except Exception as exc:
        _LOG.exception("scangroups failed")
        await _edit_safe(progress, f"❌ **Scan failed:**\n`{exc}`")
        return

    summary = (
        f"✅ **Group Scan Complete!**\n\n"
        f"🔍 **Total discovered:**     `{result['total_found']}`\n"
        f"✅ **Accessible by bot:**    `{result['accessible']}`\n"
        f"➕ **Newly added to DB:**    `{result['added_new']}`\n"
        f"🔄 **Metadata updated:**     `{result['updated']}`\n"
        f"🗑 **Stale entries pruned:** `{result['pruned']}`\n"
        f"⚠️ **Inaccessible/errors:** `{result['errors']}`\n\n"
        f"Saved to:\n"
        f"• `chatsdb` — used by /broadcast\n"
        f"• `scanned_groups` — full metadata\n\n"
        f"Use /scangroups stats to check counts anytime."
    )
    await _edit_safe(progress, summary)

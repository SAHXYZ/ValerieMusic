"""
assistantbroadcast.py  —  ValerieMusic sudo plugin

Broadcasts a message to every group the assistant userbots are in,
pins it, and automatically attaches Start Bot + Add to Group buttons.

Usage (sudo only):
    Reply to any message + /abroadcast          — send & pin silently
    Reply to any message + /abroadcast -loud    — send & pin with notification
    Reply to any message + /abroadcast -nopin   — send only, no pin
    /abroadcast <text>                          — plain text & pin silently
    /abroadcast stats                           — group count per assistant
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
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

try:
    from pyrogram.errors import ChatSendPlainForbidden as _CSPF
except ImportError:
    from pyrogram.errors import ChatWriteForbidden as _CSPF

from ValerieMusic import app
from ValerieMusic.misc import SUDOERS
from ValerieMusic.utils.database import add_served_chat, get_client

_LOG = logging.getLogger(__name__)

_VALID_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}
_SKIP_ERRORS = (
    ChannelPrivate, PeerIdInvalid, UserNotParticipant,
    ChatAdminRequired, ChatWriteForbidden, _CSPF,
)


# ── bot buttons ───────────────────────────────────────────────────────────────

def _bot_buttons() -> InlineKeyboardMarkup:
    """
    Attached to every broadcast message:
      Row 1 — 🚀 Start The Bot      (opens bot DM)
      Row 2 — ➕ Add Bot in Group   (opens add-to-group dialog)
    """
    username = app.username or "ValerieMusic"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Sᴛᴀʀᴛ Tʜᴇ Bᴏᴛ",
                url=f"https://t.me/{username}?start=start",
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Aᴅᴅ Bᴏᴛ ɪɴ Gʀᴏᴜᴘ",
                url=f"https://t.me/{username}?startgroup=true",
            )
        ],
    ])


# ── helpers ───────────────────────────────────────────────────────────────────

async def _edit_safe(msg: Message, text: str):
    try:
        await msg.edit_text(text, disable_web_page_preview=True)
    except Exception:
        pass


async def _try_pin(sent_msg: Message, loud: bool) -> bool:
    try:
        await sent_msg.pin(disable_notification=not loud)
        return True
    except Exception:
        return False


# ── core broadcast ────────────────────────────────────────────────────────────

async def _run_broadcast(
    source_chat_id,
    source_msg_id,
    plain_text,
    pin: bool,
    loud_pin: bool,
    progress: Message,
) -> dict:
    from ValerieMusic.core.userbot import assistants

    sent = pinned = failed = skipped = 0
    seen: set = set()
    buttons = _bot_buttons()

    for idx, num in enumerate(assistants, 1):
        client = await get_client(num)
        if client is None:
            continue

        await _edit_safe(
            progress,
            f"📡 **Broadcasting via Assistant {idx}/{len(assistants)}…**\n"
            f"✅ Sent: `{sent}` | 📌 Pinned: `{pinned}` | ❌ Failed: `{failed}`",
        )

        try:
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if chat.type not in _VALID_TYPES:
                    continue
                if chat.id in seen:
                    continue
                seen.add(chat.id)

                try:
                    if plain_text:
                        m = await client.send_message(
                            chat.id,
                            plain_text,
                            reply_markup=buttons,
                            disable_web_page_preview=True,
                        )
                    else:
                        m = await client.copy_message(
                            chat_id=chat.id,
                            from_chat_id=source_chat_id,
                            message_id=source_msg_id,
                            reply_markup=buttons,
                        )

                    sent += 1
                    await add_served_chat(chat.id)

                    if pin and m:
                        if await _try_pin(m, loud_pin):
                            pinned += 1

                    await asyncio.sleep(0.3)

                except FloodWait as fw:
                    wait = getattr(fw, "value", None) or getattr(fw, "x", 5)
                    if wait > 180:
                        skipped += 1
                        continue
                    await asyncio.sleep(wait + 2)
                    try:
                        if plain_text:
                            m = await client.send_message(
                                chat.id, plain_text,
                                reply_markup=buttons,
                                disable_web_page_preview=True,
                            )
                        else:
                            m = await client.copy_message(
                                chat_id=chat.id,
                                from_chat_id=source_chat_id,
                                message_id=source_msg_id,
                                reply_markup=buttons,
                            )
                        sent += 1
                        await add_served_chat(chat.id)
                        if pin and m:
                            if await _try_pin(m, loud_pin):
                                pinned += 1
                    except Exception:
                        failed += 1

                except _SKIP_ERRORS:
                    skipped += 1

                except Exception as e:
                    _LOG.debug(f"abroadcast {chat.id}: {e}")
                    failed += 1

        except FloodWait as fw:
            await asyncio.sleep(getattr(fw, "value", 5) + 2)
        except Exception as exc:
            _LOG.warning(f"Assistant {num} dialogs failed: {exc}")

    return {"sent": sent, "pinned": pinned, "failed": failed,
            "skipped": skipped, "total": len(seen)}


# ── command ───────────────────────────────────────────────────────────────────

@app.on_message(
    filters.command(["abroadcast", "assistantbroadcast"]) & SUDOERS
)
async def assistant_broadcast_cmd(client, message: Message):
    args_raw = message.text.split(None, 1)[1] if len(message.command) > 1 else ""

    # stats subcommand
    if args_raw.strip().lower() == "stats":
        from ValerieMusic.core.userbot import assistants
        lines = ["📊 **Assistant Group Stats**\n"]
        total = 0
        for num in assistants:
            c = await get_client(num)
            if c is None:
                continue
            count = 0
            async for dialog in c.get_dialogs():
                if dialog.chat.type in _VALID_TYPES:
                    count += 1
            lines.append(f"• Assistant {num}: `{count}` groups")
            total += count
        lines.append(f"\n**Total (with overlap):** `{total}`")
        return await message.reply_text("\n".join(lines))

    # flags
    loud_pin = "-loud"  in message.text
    no_pin   = "-nopin" in message.text
    pin      = not no_pin

    clean = args_raw
    for f in ("-loud", "-nopin"):
        clean = clean.replace(f, "")
    clean = clean.strip()

    # resolve content
    if message.reply_to_message:
        source_chat_id = message.chat.id
        source_msg_id  = message.reply_to_message.id
        plain_text     = None
    elif clean:
        source_chat_id = source_msg_id = None
        plain_text = clean
    else:
        return await message.reply_text(
            "❌ Reply to a message or provide text.\n\n"
            "**Usage:**\n"
            "`/abroadcast` — reply to a message\n"
            "`/abroadcast <text>` — plain text\n"
            "`/abroadcast -nopin` — no pin\n"
            "`/abroadcast -loud` — pin with notification\n"
            "`/abroadcast stats` — group counts"
        )

    pin_note = "📌 silent pin" if (pin and not loud_pin) else ("📣 loud pin" if loud_pin else "no pin")
    progress = await message.reply_text(
        f"📡 **Assistant Broadcast Starting…**\n"
        f"Mode: {pin_note} | Buttons: 🚀 Start Bot + ➕ Add to Group\n\n"
        f"Walking assistant dialogs…"
    )

    try:
        result = await _run_broadcast(
            source_chat_id=source_chat_id,
            source_msg_id=source_msg_id,
            plain_text=plain_text,
            pin=pin,
            loud_pin=loud_pin,
            progress=progress,
        )
    except Exception as exc:
        _LOG.exception("abroadcast failed")
        return await _edit_safe(progress, f"❌ **Broadcast failed:**\n`{exc}`")

    pin_line = f"📌 **Pinned in:** `{result['pinned']}` chats\n" if pin else ""
    await _edit_safe(
        progress,
        f"✅ **Assistant Broadcast Complete!**\n\n"
        f"📨 **Sent to:**   `{result['sent']}` groups\n"
        f"{pin_line}"
        f"⏭ **Skipped:**  `{result['skipped']}` (restricted/flood)\n"
        f"❌ **Failed:**   `{result['failed']}`\n\n"
        f"💾 All reached chats added to DB — `/broadcast` will reach them next time too.",
    )

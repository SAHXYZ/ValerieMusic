# ValerieMusic — Purge Tools (ported from ValerieBot userbot)
# /purge — reply to a message; deletes everything from there up to your command.
# /del   — delete the replied message.
# NOTE: a bot can only delete messages when it is an admin with "Delete Messages".
#       Unlike a userbot it cannot scan history, so purge works by message-id range.

import asyncio

from pyrogram import filters
from pyrogram.errors import RPCError

from ValerieMusic import app
from config import BANNED_USERS

SEP = "━" * 20


@app.on_message(filters.command(["purge"]) & filters.group & ~BANNED_USERS)
async def cmd_purge(client, message):
    reply = message.reply_to_message
    if not reply:
        return await message.reply_text(
            "<b>Usage:</b> reply to a message with <code>/purge</code> to delete "
            "everything from there up to your command.\n"
            "<i>The bot must be admin with delete permission.</i>"
        )

    from_id = reply.id
    to_id = message.id
    ids = list(range(from_id, to_id + 1))

    deleted = 0
    # Telegram allows deleting up to 100 ids per call.
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            deleted += await app.delete_messages(message.chat.id, chunk)
        except RPCError:
            pass
        await asyncio.sleep(0.2)

    try:
        notif = await app.send_message(
            message.chat.id, f"🗑 <b>Purged {deleted} messages.</b>"
        )
        await asyncio.sleep(3)
        await notif.delete()
    except Exception:
        pass


@app.on_message(filters.command(["del"]) & ~BANNED_USERS)
async def cmd_del(client, message):
    reply = message.reply_to_message
    if not reply:
        return await message.reply_text("❌ <i>Reply to a message to delete it.</i>")
    try:
        await app.delete_messages(message.chat.id, [reply.id, message.id])
    except RPCError as e:
        await message.reply_text(f"❌ <i>Could not delete:</i> <code>{e}</code>")

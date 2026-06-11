# ValerieMusic — AFK (ported & adapted from ValerieBot userbot)
# Public & per-user: ANY user can /afk. When they're mentioned or replied to,
# the bot announces they're away; their next message clears it automatically.

import time

from pyrogram import filters
from pyrogram.enums import ChatType

from ValerieMusic import app
from ValerieMusic.utils.formatters import get_readable_time
from config import BANNED_USERS

SEP = "━" * 20

# In-memory state: user_id -> {"since": ts, "reason": str}
_afk: dict = {}
# Auto-reply cooldown: (target_id, chat_id) -> ts
_replied: dict = {}
REPLY_COOL = 60


@app.on_message(filters.command(["afk"]) & ~BANNED_USERS, group=8)
async def cmd_afk(client, message):
    user = message.from_user
    if not user:
        return
    parts = (message.text or "").split(None, 1)
    reason = parts[1].strip() if len(parts) > 1 else "Not specified"
    _afk[user.id] = {
        "since": time.time(),
        "reason": reason,
        "username": (user.username or "").lower(),
    }
    await message.reply_text(
        f"😴 <b>{user.first_name} is now AFK</b>\n{SEP}\n"
        f"◆ Reason → <i>{reason}</i>\n\n"
        "<i>Send any message to come back.</i>"
    )


@app.on_message(filters.command(["unafk"]) & ~BANNED_USERS, group=8)
async def cmd_unafk(client, message):
    user = message.from_user
    if not user:
        return
    if user.id not in _afk:
        return await message.reply_text("⚠️ <i>You are not AFK.</i>")
    duration = get_readable_time(int(time.time() - _afk[user.id]["since"]))
    _afk.pop(user.id, None)
    await message.reply_text(
        f"✅ <b>Welcome back, {user.first_name}!</b>\n{SEP}\n"
        f"◆ AFK duration → <code>{duration}</code>"
    )


@app.on_message(
    (filters.group | filters.private) & filters.incoming & ~filters.bot & ~BANNED_USERS,
    group=9,
)
async def afk_watcher(client, message):
    user = message.from_user
    if not user:
        return

    text = message.text or message.caption or ""

    # 1) The AFK user came back (any message that isn't /afk).
    if user.id in _afk:
        low = text.lower().lstrip("/!.")
        if not low.startswith("afk"):
            duration = get_readable_time(int(time.time() - _afk[user.id]["since"]))
            _afk.pop(user.id, None)
            try:
                notif = await message.reply_text(
                    f"✅ <b>{user.first_name} is back!</b> "
                    f"<i>(was AFK for {duration})</i>"
                )
                import asyncio
                await asyncio.sleep(5)
                await notif.delete()
            except Exception:
                pass

    if not _afk:
        return

    # 2) Find which AFK users were targeted: reply, @username, or text-mention.
    targets = set()
    if message.reply_to_message and message.reply_to_message.from_user:
        rid = message.reply_to_message.from_user.id
        if rid in _afk and rid != user.id:
            targets.add(rid)

    for ent in (message.entities or []):
        if ent.type and ent.user and ent.user.id in _afk:
            targets.add(ent.user.id)

    if "@" in text and message.chat.type != ChatType.PRIVATE:
        for word in text.split():
            if word.startswith("@") and len(word) > 1:
                uname = word[1:].lower().rstrip(".,!?")
                for uid, st in _afk.items():
                    if st.get("username") == uname and uid != user.id:
                        targets.add(uid)

    now = time.time()
    for tid in targets:
        ck = (tid, message.chat.id)
        if now - _replied.get(ck, 0) < REPLY_COOL:
            continue
        _replied[ck] = now
        st = _afk.get(tid)
        if not st:
            continue
        duration = get_readable_time(int(now - st["since"]))
        try:
            await message.reply_text(
                f"😴 <b>That user is AFK</b>\n{SEP}\n"
                f"◆ Reason → <i>{st['reason']}</i>\n"
                f"◆ Since  → <code>{duration}</code> ago"
            )
        except Exception:
            pass

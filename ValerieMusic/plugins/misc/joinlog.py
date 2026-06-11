from pyrogram.types import ChatMemberUpdated
from datetime import datetime, timedelta, timezone

from ValerieMusic import app
from config import LOG_GROUP_ID


# Indian timezone (no pytz)
IST = timezone(timedelta(hours=5, minutes=30))


@app.on_chat_member_updated()
async def bot_added_log(_, update: ChatMemberUpdated):
    try:
        new = update.new_chat_member
        old = update.old_chat_member

        # Only run when THIS bot is added
        if not new or not new.user or new.user.id != app.id:
            return

        # Ignore if bot was already a member before
        if old and old.status in ["member", "administrator"]:
            return

        chat = update.chat
        adder = update.from_user

        # Chat Link
        if chat.username:
            chat_link = f"https://t.me/{chat.username}"
        else:
            chat_link = "No Public Link"

        # Date & Time (IST)
        now = datetime.now(IST)
        date = now.strftime("%d-%b-%Y")
        time = now.strftime("%I:%M %p")

        # Message Format
        text = f"""
⟐────────────────────────────⟐
  ⌬ Nᴇᴡ Gʀᴏᴜᴘ Aᴅᴅᴇᴅ Tᴏ Tʜᴇ Bᴏᴛ ⌬
⟐─────────────────────────────⟐

⟣ Cʜᴀᴛ Tɪᴛʟᴇ : {chat.title}
──────────────⟐
⟢ Cʜᴀᴛ Iᴅ : <code>{chat.id}</code>
──────────────⟐
⟡ Cʜᴀᴛ Lɪɴᴋ : {chat_link}
──────────────⟐
⟠ Aᴅᴅᴇᴅ Bʏ : {adder.mention if adder else "Unknown"}
──────────────⟐
⟡ Uꜱᴇʀ : {new.user.mention}
──────────────⟐
⟞ Dᴀᴛᴇ : {date}
⟟ Tɪᴍᴇ : {time}
⟪ Lᴏɢ : Nᴇᴡ Aᴄᴛɪᴠᴇ Gʀᴏᴜᴘ Aᴅᴅᴇᴅ 
──────────────⟐
"""

        await app.send_message(
            LOG_GROUP_ID,
            text,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"[JoinLogError] {e}")

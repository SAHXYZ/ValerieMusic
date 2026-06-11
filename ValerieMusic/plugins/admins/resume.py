from pyrogram import filters
from pyrogram.types import Message

from ValerieMusic import app
from ValerieMusic.core.call import Valerie
from ValerieMusic.utils.database import is_music_playing, music_on
from ValerieMusic.utils.decorators import AdminRightsCheck
from ValerieMusic.utils.inline import close_markup
from config import BANNED_USERS, RESUME_IMG


@app.on_message(filters.command(["resume", "cresume"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def resume_com(cli, message: Message, _, chat_id):
    if await is_music_playing(chat_id):
        return await message.reply_text(_["admin_3"])
    await music_on(chat_id)
    await Valerie.resume_stream(chat_id)
    await message.reply_photo(
        photo=RESUME_IMG,
        caption=_["admin_4"].format(message.from_user.mention),
        reply_markup=close_markup(_),
    )

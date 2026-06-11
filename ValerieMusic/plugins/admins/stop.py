from pyrogram import filters
from pyrogram.types import Message

from ValerieMusic import app
from ValerieMusic.core.call import Valerie
from ValerieMusic.utils.database import set_loop
from ValerieMusic.utils.decorators import AdminRightsCheck
from ValerieMusic.utils.inline import close_markup
from config import BANNED_USERS, END_IMG


@app.on_message(
    filters.command(["end", "stop", "cend", "cstop"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def stop_music(cli, message: Message, _, chat_id):
    if not len(message.command) == 1:
        return
    await Valerie.stop_stream(chat_id)
    await set_loop(chat_id, 0)
    await message.reply_photo(
        photo=END_IMG,
        caption=_["admin_5"].format(message.from_user.mention),
        reply_markup=close_markup(_),
    )

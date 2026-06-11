import time

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython.__future__ import VideosSearch

import config
from ValerieMusic import app
from ValerieMusic.misc import _boot_
from ValerieMusic.plugins.sudo.sudoers import sudoers_list
from ValerieMusic.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from ValerieMusic.utils import bot_sys_stats
from ValerieMusic.utils.decorators.language import LanguageStart
from ValerieMusic.utils.formatters import get_readable_time
from ValerieMusic.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS
from strings import get_string


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]

        if name.startswith("help"):
            keyboard = help_pannel(_)
            return await message.reply_photo(
                photo=config.HELP_IMG,
                caption=_["help_1"].format(config.SUPPORT_GROUP),
                reply_markup=keyboard,
            )

        if name.startswith("sud"):
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOG_GROUP_ID,
                    text=f"{message.from_user.mention} checked <b>SudoList</b>\n<b>ID:</b> <code>{message.from_user.id}</code>",
                )
            return

        if name.startswith("inf"):
            m = await message.reply_text("🔎 Searching...")
            query = name.replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"

            results = VideosSearch(query, limit=1)
            for result in (await results.next())["result"]:
                title = result["title"]
                duration = result["duration"]
                views = result["viewCount"]["short"]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                channellink = result["channel"]["link"]
                channel = result["channel"]["name"]
                link = result["link"]
                published = result["publishedTime"]

            searched_text = _["start_6"].format(
                title, duration, views, published, channellink, channel, app.mention
            )

            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text=_["S_B_8"], url=link),
                        InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_GROUP),
                    ]
                ]
            )

            await m.delete()
            await app.send_photo(
                chat_id=message.chat.id,
                photo=thumbnail,
                caption=searched_text,
                reply_markup=key,
            )
            return

    # Normal /start (no arguments)
    out = private_panel(_)
    UP, CPU, RAM, DISK = await bot_sys_stats()

    try:
        print("[DEBUG LOADED START_2] =>", _["start_2"][:200])
    except Exception as e:
        print("[DEBUG ERROR]", e)

    await message.reply_photo(
        photo=config.START_IMG_URL,
        caption=_["start_2"].format(
            message.from_user.mention,
            app.mention,
            UP,
            DISK,
            CPU,
            RAM,
        ),
        reply_markup=InlineKeyboardMarkup(out),
    )

    # ============================================
    # 🔥 CUSTOM PREMIUM LOG MESSAGE
    # ============================================

    if await is_on_off(2):
        bot_username = app.username
        user = message.from_user
        username = user.username if user.username else "No_Username"

        log_text = (
            "┏━━━──────────➣\n"
            "╰➢ 🜲 S T A R T   L O G\n"
            "┆\n"
            f"┠─▹ Bot ⥈ @{bot_username}\n"
            "┆ \n"
            "┠─▹ #Aᴄᴛɪᴠᴀᴛᴇᴅ_ᴛʜᴇ_ʙᴏᴛ\n"
            "┆\n"
            "┏━━━────────────➣\n"
            "╰➢ 🜲 U S E R   I N F O\n"
            "┆\n"
            f"┠─▹ Nᴀᴍᴇ ⥈ {user.mention}\n"
            "┆\n"
            f"┠─▹ Iᴅ ⥈ {user.id}\n"
            "┆\n"
            f"┠─▹ Tᴀɢ ⥈ @{username}\n"
            "┆\n"
            "┗━━━━━━❪ ⌬ ❫━━━━━━━➣"
        )

        await app.send_message(
            chat_id=config.LOG_GROUP_ID,
            text=log_text,
            disable_web_page_preview=True
        )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    await message.reply_photo(
        photo=config.START_IMG_URL,
        caption=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
    )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass

            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)

                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_GROUP,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                await message.reply_photo(
                    photo=config.START_IMG_URL,
                    caption=_["start_3"].format(
                        message.from_user.first_name,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )

                await add_served_chat(message.chat.id)
                await message.stop_propagation()

        except Exception as ex:
            print(ex)

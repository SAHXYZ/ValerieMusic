from typing import Union

from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, Message
from pyrogram.errors import MessageNotModified

from ValerieMusic import app
from ValerieMusic.utils import bot_sys_stats, help_pannel
from ValerieMusic.utils.database import get_lang
from ValerieMusic.utils.decorators.language import LanguageStart, languageCB
from ValerieMusic.utils.inline.help import private_help_panel
from ValerieMusic.utils.inline.start import private_panel
from config import BANNED_USERS, START_IMG_URL, SUPPORT_GROUP, HELP_IMG
from strings import get_string, helpers


# ================= PRIVATE HELP =================
@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("settings_back_helper") & ~BANNED_USERS)
async def helper_private(client: app, update: Union[types.Message, types.CallbackQuery]):

    is_callback = isinstance(update, types.CallbackQuery)

    if is_callback:
        await update.answer()
        chat_id = update.message.chat.id
        language = await get_lang(chat_id)
        _ = get_string(language)

        try:
            await update.edit_message_caption(
                caption=_["help_1"].format(SUPPORT_GROUP),
                reply_markup=help_pannel(_),
            )
        except MessageNotModified:
            pass
        except Exception:
            pass

    else:
        language = await get_lang(update.chat.id)
        _ = get_string(language)

        await update.reply_photo(
            photo=HELP_IMG,
            caption=_["help_1"].format(SUPPORT_GROUP),
            reply_markup=help_pannel(_),
        )


# ================= GROUP HELP =================
@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client, message: Message, _):
    keyboard = private_help_panel(_)
    await message.reply_text(_["help_2"], reply_markup=InlineKeyboardMarkup(keyboard))


# ================= CALLBACK =================
# ---- safe edit: help message is a PHOTO, so prefer caption edit ----
async def _safe_edit(CallbackQuery, text, reply_markup):
    """Edit help message. The panel is a photo, so plain edit_message_text
    fails on it; try caption first, fall back to text, swallow not-modified."""
    try:
        return await CallbackQuery.edit_message_caption(
            caption=text, reply_markup=reply_markup
        )
    except MessageNotModified:
        return
    except Exception:
        pass
    try:
        return await CallbackQuery.edit_message_text(
            text, reply_markup=reply_markup
        )
    except MessageNotModified:
        return
    except Exception:
        return


@app.on_callback_query(filters.regex("help_callback") & ~BANNED_USERS)
@languageCB
async def helper_cb(client, CallbackQuery, _):

    cb = CallbackQuery.data.split()[1]

    from ValerieMusic.utils.inline.help import (
        users_menu,
        admin_menu,
        extra_menu,
        extra_back_menu,
        play_user_menu,
        ping_user_menu,
        cplay_user_menu,
        playlist_user_menu,
        song_user_menu,
        play_admin_menu,
        cplay_admin_menu,
        auth_admin_menu,
    )

    # ===== MAIN =====
    if cb == "users":
        return await _safe_edit(CallbackQuery, 
            "👤 User Commands",
            reply_markup=users_menu(),
        )

    elif cb == "admin":
        chat = CallbackQuery.message.chat

        if chat.type in ["group", "supergroup"]:
            member = await app.get_chat_member(chat.id, CallbackQuery.from_user.id)
            if member.status not in ["administrator", "creator"]:
                return await CallbackQuery.answer("Admins only", show_alert=True)

        return await _safe_edit(CallbackQuery, 
            "🛡 Admin Commands",
            reply_markup=admin_menu(),
        )

    # ===== EXTRA (public tools) =====
    elif cb == "extra" or cb == "back_extra":
        return await _safe_edit(CallbackQuery,
            "🛠 Extra Commands — available to everyone",
            reply_markup=extra_menu(),
        )

    elif cb == "ex_imagine":
        return await _safe_edit(CallbackQuery, helpers.HELP_E1, reply_markup=extra_back_menu())
    elif cb == "ex_mmf":
        return await _safe_edit(CallbackQuery, helpers.HELP_E2, reply_markup=extra_back_menu())
    elif cb == "ex_sticker":
        return await _safe_edit(CallbackQuery, helpers.HELP_E3, reply_markup=extra_back_menu())
    elif cb == "ex_kang":
        return await _safe_edit(CallbackQuery, helpers.HELP_E4, reply_markup=extra_back_menu())
    elif cb == "ex_purge":
        return await _safe_edit(CallbackQuery, helpers.HELP_E5, reply_markup=extra_back_menu())
    elif cb == "ex_afk":
        return await _safe_edit(CallbackQuery, helpers.HELP_E6, reply_markup=extra_back_menu())

    # ===== BACK =====
    elif cb == "home":
        UP, CPU, RAM, DISK = await bot_sys_stats()
        return await _safe_edit(
            CallbackQuery,
            _["start_2"].format(
                CallbackQuery.from_user.mention, app.mention, UP, DISK, CPU, RAM
            ),
            reply_markup=InlineKeyboardMarkup(private_panel(_)),
        )

    elif cb == "back_main":
        return await _safe_edit(CallbackQuery, 
            _["help_1"].format(SUPPORT_GROUP),
            reply_markup=help_pannel(_),
        )

    elif cb == "back_users":
        return await _safe_edit(CallbackQuery, 
            "👤 User Commands",
            reply_markup=users_menu(),
        )

    elif cb == "back_admin":
        return await _safe_edit(CallbackQuery, 
            "🛡 Admin Commands",
            reply_markup=admin_menu(),
        )

    # ===== USER SUBMENUS =====
    elif cb == "user_play":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_11,
            reply_markup=play_user_menu(),
        )

    elif cb == "user_ping":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_10,
            reply_markup=ping_user_menu(),
        )

    elif cb == "user_cplay":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_6,
            reply_markup=cplay_user_menu(),
        )

    elif cb == "user_playlist":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_15,
            reply_markup=playlist_user_menu(),
        )

    elif cb == "user_song":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_14,
            reply_markup=song_user_menu(),
        )

    # ===== ADMIN SUBMENUS =====
    elif cb == "admin_play":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_1,
            reply_markup=play_admin_menu(),
        )

    elif cb == "admin_cplay":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_6,
            reply_markup=cplay_admin_menu(),
        )

    elif cb == "admin_auth":
        return await _safe_edit(CallbackQuery, 
            helpers.HELP_2,
            reply_markup=auth_admin_menu(),
        )

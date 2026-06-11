from typing import Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from ValerieMusic import app


# ================= MAIN =================
def help_pannel(_, START: Union[bool, int] = None):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Users", callback_data="help_callback users"),
            InlineKeyboardButton("🛡 Admin", callback_data="help_callback admin"),
        ],
        [
            InlineKeyboardButton("🛠 Extra", callback_data="help_callback extra"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="help_callback home"),
        ],
    ])


# ================= EXTRA (public tools) =================
def extra_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 Imagine", callback_data="help_callback ex_imagine"),
            InlineKeyboardButton("✍️ MMF", callback_data="help_callback ex_mmf"),
        ],
        [
            InlineKeyboardButton("🏷 Sticker", callback_data="help_callback ex_sticker"),
            InlineKeyboardButton("📦 Kang", callback_data="help_callback ex_kang"),
        ],
        [
            InlineKeyboardButton("🧹 Purge", callback_data="help_callback ex_purge"),
            InlineKeyboardButton("😴 AFK", callback_data="help_callback ex_afk"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="help_callback back_main"),
        ],
    ])


def extra_back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_extra")]
    ])


# ================= USERS =================
def users_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Play", callback_data="help_callback user_play"),
            InlineKeyboardButton("⚡ Ping", callback_data="help_callback user_ping"),
        ],
        [
            InlineKeyboardButton("🎵 C-Play", callback_data="help_callback user_cplay"),
            InlineKeyboardButton("📂 Playlist", callback_data="help_callback user_playlist"),
        ],
        [
            InlineKeyboardButton("🎧 Song", callback_data="help_callback user_song"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="help_callback back_main"),
        ]
    ])


# ================= ADMIN =================
def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Play", callback_data="help_callback admin_play"),
            InlineKeyboardButton("🎵 C-Play", callback_data="help_callback admin_cplay"),
        ],
        [
            InlineKeyboardButton("🔐 Auth", callback_data="help_callback admin_auth"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="help_callback back_main"),
        ]
    ])


# ================= USER SUBMENUS =================
def play_user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Queue", callback_data="help_callback hb23")],
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_users")]
    ])

def ping_user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_users")]
    ])

def cplay_user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_users")]
    ])

def playlist_user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_users")]
    ])

def song_user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_users")]
    ])


# ================= ADMIN SUBMENUS =================
def play_admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause", callback_data="help_callback hb18"),
            InlineKeyboardButton("▶️ Resume", callback_data="help_callback hb19"),
        ],
        [
            InlineKeyboardButton("⏭ Skip", callback_data="help_callback hb20"),
            InlineKeyboardButton("⏹ Stop", callback_data="help_callback hb21"),
        ],
        [
            InlineKeyboardButton("🎛 Player", callback_data="help_callback hb22"),
            InlineKeyboardButton("📜 Queue", callback_data="help_callback hb23"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_admin")]
    ])

def cplay_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_admin")]
    ])

def auth_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help_callback back_admin")]
    ])


# ================= PRIVATE =================
def private_help_panel(_):
    return [
        [
            InlineKeyboardButton(
                text=_["S_B_4"],
                url=f"https://t.me/{app.username}?start=help",
            ),
        ],
    ]


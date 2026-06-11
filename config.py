import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")

# Get your token from @BotFather on Telegram.
BOT_TOKEN = getenv("BOT_TOKEN")

# ── MySQL database (OPTIONAL local backup) ─────────────────────────────────
# MongoDB is the primary store (set MONGO_DB_URI above). MySQL is now OPTIONAL:
# leave MYSQL_HOST blank to run on MongoDB alone. If you DO set MYSQL_HOST, the
# bot keeps a live local backup copy of every write in MySQL too — so even if
# the cloud DB is unreachable you have a second copy on the VPS.
MYSQL_HOST = getenv("MYSQL_HOST", "") or None
MYSQL_PORT = int(getenv("MYSQL_PORT", 3306))
MYSQL_USER = getenv("MYSQL_USER", "valerie")
MYSQL_PASSWORD = getenv("MYSQL_PASSWORD", "@VALERIEMSC121@")
MYSQL_DB = getenv("MYSQL_DB", "ValerieMusic")

# ── MongoDB (PRIMARY datastore) ────────────────────────────────────────────
# Recommended: use a MongoDB connection string (local mongod or a cloud cluster
# like MongoDB Atlas). With Atlas your data lives off the VPS, so if the VPS
# expires you keep all users/groups and just redeploy with the same URI.
MONGO_DB_URI = getenv("MONGO_DB_URI", None)
MONGO_DB_NAME = getenv("MONGO_DB_NAME", "ValerieMusic")

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 1700))

# Chat id of a group for logging bot's activities
LOG_GROUP_ID = int(getenv("LOG_GROUP_ID", None))

# Get this value from @MissRose_Bot on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", 0))
OWNER_USERNAME = getenv("OWNER_USERNAME", None)


## Fill these variables if you're deploying on heroku.
# Your heroku app name
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

API_URL = getenv("API_URL", "http://127.0.0.1:8003")  # YouTube song API base URL
API_KEY = getenv("API_KEY", None)  # YouTube song API key (optional)
SONG_PLAYER_URL = getenv("SONG_PLAYER_URL", "https://songs.rocksmusicapi.xyz/player")  # RocksPlayer deep-link base
VIDEO_API_URL = getenv("VIDEO_API_URL", "http://127.0.0.1:8003")
# COOKIES_URL can contain one or multiple URLs separated by spaces or commas,
# similar to TgMusicBot. Each URL should point to a text cookies file exported
# from your browser (Netscape cookie format).
COOKIES_URL = getenv("COOKIES_URL", "")
COOKIES_URLS = []
if COOKIES_URL:
    parts = re.split(r"[\s,]+", COOKIES_URL.strip())
    COOKIES_URLS = [p for p in parts if p]

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/SAHXYZ/ValerieMusic",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "master")
GIT_TOKEN = getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/Pubglovers_Shayri_lovers")
SUPPORT_GROUP = getenv("SUPPORT_GROUP", "https://t.me/+2HpAd1kBDRo1NzY1")

# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

# make your bots privacy from telegra.ph and put your url here
PRIVACY_LINK = getenv("PRIVACY_LINK", "https://telegra.ph/Privacy-Policy-for-VenomMusic-08-14")


# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", None)
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", None)


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 25))


# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 2145386496))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes


# Get your pyrogram v2 session from Replit
STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)


BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}


START_IMG_URL = getenv(
    "START_IMG_URL", "https://files.catbox.moe/rfmqxa.jpg"
)
PING_IMG_URL = getenv(
    "PING_IMG_URL", "ValerieMusic/assets/ping.jpg"
)
PLAYLIST_IMG_URL = "https://files.catbox.moe/pfjgmf.jpg"
STATS_IMG_URL = "https://files.catbox.moe/st6utj.jpg"
TELEGRAM_AUDIO_URL = "https://image2url.com/images/1764495528084-caa45f88-2e2b-490a-89b5-f327c05beb9a.jpg"
TELEGRAM_VIDEO_URL = "https://graph.org//file/2f7debf856695e0ef0607.png"
STREAM_IMG_URL = "https://te.legra.ph/file/bd995b032b6bd263e2cc9.jpg"
SOUNCLOUD_IMG_URL = "https://te.legra.ph/file/bb0ff85f2dd44070ea519.jpg"
YOUTUBE_IMG_URL = "https://image2url.com/images/1764495528084-caa45f88-2e2b-490a-89b5-f327c05beb9a.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://te.legra.ph/file/37d163a2f75e0d3b403d6.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://te.legra.ph/file/b35fd1dfca73b950b1b05.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://te.legra.ph/file/95b3ca7993bbfaf993dcb.jpg"

# ===== Action word-art images =====
# Set these in .env as e.g. SKIP=https://.../skip.png to override.
# If left unset or blank, the bundled assets are used.
SKIP_IMG = getenv("SKIP") or "ValerieMusic/assets/Skip.png"
PAUSE_IMG = getenv("PAUSE") or "ValerieMusic/assets/Pause.png"
RESUME_IMG = getenv("RESUME") or "ValerieMusic/assets/Resume.png"
END_IMG = getenv("END") or "ValerieMusic/assets/End.png"
HELP_IMG = getenv("HELP") or "ValerieMusic/assets/Help.png"
# Base now-playing thumbnail (the frame with the white cover box). Optional URL;
# it is downloaded and cached locally once, since it must be a real file on disk
# for the cover to be composited into it.
THUMBNAIL_URL = getenv("THUMBNAIL") or None


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))


if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_GROUP:
    if not re.match("(?:http|https)://", SUPPORT_GROUP):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_GROUP url is wrong. Please ensure that it starts with https://"
        )

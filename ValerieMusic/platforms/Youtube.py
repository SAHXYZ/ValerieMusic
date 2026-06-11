import re
import os
import asyncio
import aiohttp
from typing import Union
from urllib.parse import quote

import yt_dlp

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from youtubesearchpython.__future__ import VideosSearch, Playlist

from ValerieMusic.utils.formatters import time_to_seconds
from config import API_URL, API_KEY

# ── in-memory search cache ────────────────────────────────────
SEARCH_CACHE = {}

# Cookies file — same path used by ytdlp.py
COOKIES_PATH = os.path.join(os.getcwd(), "cookies.txt")


# ── helpers ───────────────────────────────────────────────────
def extract_video_id(link: str) -> Union[str, None]:
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]
    if "watch?v=" in link:
        return link.split("v=")[-1].split("&")[0]
    return None


# ──────────────────────────────────────────────────────────────
# search_with_ytdlp
#
# Uses yt-dlp with cookies to search YouTube and return the
# best matching video's metadata.
#
# WHY: youtubesearchpython has no cookies → crashes or returns
# wrong results for latest/regional/restricted songs.
# yt-dlp with cookies = same engine that makes direct links work.
#
# Runs in a thread executor so it doesn't block the event loop.
# ──────────────────────────────────────────────────────────────
def _ytdlp_search_sync(query: str) -> Union[dict, None]:
    """Sync yt-dlp search — run via run_in_executor."""
    ydl_opts = {
        "quiet":           True,
        "no_warnings":     True,
        "extract_flat":    True,   # don't fetch full info, just search metadata
        "noplaylist":      True,
        "cookiefile":      COOKIES_PATH if os.path.exists(COOKIES_PATH) else None,
        "source_address":  "0.0.0.0",
        "nocheckcertificate": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not info or not info.get("entries"):
                return None
            entry = info["entries"][0]
            if not entry:
                return None

            vid      = entry.get("id", "")
            title    = entry.get("title", query)
            duration = entry.get("duration") or 0   # seconds int
            thumb    = entry.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

            if not vid:
                return None

            mins = int(duration) // 60
            secs = int(duration) % 60
            duration_min = f"{mins}:{secs:02d}"

            return {
                "title":        title,
                "link":         f"https://www.youtube.com/watch?v={vid}",
                "vidid":        vid,
                "duration_min": duration_min,
                "thumb":        thumb,
                "duration_sec": int(duration),
            }
    except Exception as e:
        print(f"_ytdlp_search_sync error: {e}")
        return None


async def search_with_ytdlp(query: str) -> Union[dict, None]:
    """Async wrapper around _ytdlp_search_sync."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _ytdlp_search_sync, query)


# ──────────────────────────────────────────────────────────────
# fetch_stream — talks to RocksAPI backend
# ──────────────────────────────────────────────────────────────
async def fetch_stream(query: str, video: bool = False) -> Union[str, None]:
    query = query.strip()
    if not query:
        return None

    endpoint = "video" if video else "audio"
    api_url = f"{API_URL}/api/{endpoint}?query={quote(query)}"

    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    timeout = aiohttp.ClientTimeout(total=60)

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(api_url, headers=headers) as resp:

                    if resp.status == 429:
                        await asyncio.sleep(3 * (attempt + 1))
                        continue

                    if resp.status in (401, 403):
                        print(f"AUTH/FORBIDDEN [{endpoint}]: {(await resp.text())[:100]}")
                        return None

                    if resp.status != 200:
                        print(f"API ERROR [{endpoint}]: HTTP {resp.status}")
                        await asyncio.sleep(2)
                        continue

                    data = await resp.json()

                    if video:
                        stream = (data.get("audioUrl") or "").strip() or data.get("streamUrl", "").strip()
                    else:
                        stream = data.get("streamUrl", "").strip()

                    print(f"API [{endpoint}]: {data.get('title','?')} → {(stream or 'EMPTY')[:80]}")

                    if stream:
                        return stream

                    if video:
                        print("API [video]: empty — falling back to /api/audio")
                        return await fetch_stream(query, video=False)

                    await asyncio.sleep(2)

        except asyncio.TimeoutError:
            print(f"TIMEOUT [{endpoint}] attempt {attempt + 1}")
        except Exception as e:
            print(f"FETCH ERROR [{endpoint}] attempt {attempt + 1}: {e}")

        if attempt < 2:
            await asyncio.sleep(3)

    print(f"FETCH FAILED [{endpoint}]: {query[:60]}")
    return None


async def fetch_audio_stream(query: str) -> Union[str, None]:
    return await fetch_stream(query, video=False)


# ──────────────────────────────────────────────────────────────
# YouTubeAPI class
# ──────────────────────────────────────────────────────────────
class YouTubeAPI:
    def __init__(self):
        self.base     = "https://www.youtube.com/watch?v="
        self.regex    = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg      = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)
        for msg in messages:
            entities = msg.entities or msg.caption_entities or []
            text = msg.text or msg.caption or ""
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    url = text[ent.offset : ent.offset + ent.length]
                    return url.split("?si=")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    async def track(self, link: str, videoid: Union[bool, str] = None):
        """
        Resolve a search query or YouTube URL to track metadata.

        Search priority:
          1. youtubesearchpython  — fast, works for most songs
          2. yt-dlp search        — uses cookies, works for latest /
                                    restricted / regional songs
        Never raises an exception.
        """
        if videoid:
            link = self.base + link

        link = link.split("&")[0]
        cache_key = link.lower()

        if cache_key in SEARCH_CACHE:
            return SEARCH_CACHE[cache_key]

        # ── 1. Try youtubesearchpython ────────────────────────────
        try:
            results = VideosSearch(link, limit=1)
            raw = (await results.next())["result"]

            if raw and raw[0].get("id") and raw[0].get("duration"):
                data         = raw[0]
                duration_min = data["duration"]
                duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0

                result = ({
                    "title":        data["title"],
                    "link":         data["link"],
                    "vidid":        data["id"],
                    "duration_min": duration_min,
                    "thumb":        data["thumbnails"][0]["url"].split("?")[0],
                    "duration_sec": duration_sec,
                }, data["id"])

                SEARCH_CACHE[cache_key] = result
                return result

            print(f"TRACK: youtubesearchpython empty/incomplete for: {link[:50]}")

        except Exception as e:
            print(f"TRACK: youtubesearchpython failed for '{link[:50]}': {e}")

        # ── 2. yt-dlp search with cookies ─────────────────────────
        print(f"TRACK: trying yt-dlp search for: {link[:50]}")
        data = await search_with_ytdlp(link)

        if data:
            result = (data, data["vidid"])
            SEARCH_CACHE[cache_key] = result
            print(f"TRACK: yt-dlp found: {data['title'][:50]}")
            return result

        # ── 3. Last resort dummy — download() handles stream ──────
        print(f"TRACK: all search methods failed for '{link[:50]}' — using dummy")
        dummy_result = ({
            "title":        link,
            "link":         "",
            "vidid":        "__search__",
            "duration_min": "0:00",
            "thumb":        "https://i.ytimg.com/vi/default/hqdefault.jpg",
            "duration_sec": 0,
        }, "__search__")
        return dummy_result

    async def details(self, link: str, videoid: Union[bool, str] = None):
        track, vid = await self.track(link, videoid)
        return (
            track["title"],
            track["duration_min"],
            track["duration_sec"],
            track["thumb"],
            vid,
        )

    async def title(self, link: str, videoid: Union[bool, str] = None):
        track, _ = await self.track(link, videoid)
        return track["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        track, _ = await self.track(link, videoid)
        return track["duration_min"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        track, _ = await self.track(link, videoid)
        return track["thumb"]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Used for live streams."""
        if videoid:
            vid = link
        else:
            vid = extract_video_id(link)
        if not vid:
            return 0, "Invalid YouTube ID"

        yt_url = self.base + vid
        stream_url = await fetch_stream(yt_url, video=True)
        if not stream_url:
            await asyncio.sleep(3)
            stream_url = await fetch_stream(yt_url, video=True)

        if stream_url:
            return 1, stream_url
        return 0, "❌ API failed to return video stream"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        return [v["id"] for v in videos[:limit] if v and v.get("id")]

    async def slider(self, link: str, index: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        search = VideosSearch(link, limit=10)
        # FIX: ["result"][index] raised KeyError/IndexError on empty results
        # or when the ◁ ▷ slider index overran. Guard it; keep the 4-tuple
        # contract so callers never crash on unpack.
        try:
            results = (await search.next()).get("result") or []
        except Exception:
            results = []
        if not results:
            return ("No results", "0:00", "https://i.ytimg.com/vi/default/hqdefault.jpg", "")
        result = results[index % len(results)]
        return (
            result["title"],
            result["duration"],
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"],
        )

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        **kwargs,
    ):
        """
        Main entry point for /play and /vplay.

        - videoid=True + real ID  → exact YouTube URL → backend
        - YouTube URL             → extract ID → exact URL → backend
        - Plain query / __search__ dummy → yt-dlp search (with cookies)
          to resolve to a YouTube URL, then send that to backend
        """
        want_video = bool(video)

        if videoid and link != "__search__":
            # Known video ID — send exact URL
            yt_url = self.base + link
            stream_url = await fetch_stream(yt_url, video=want_video)
            if not stream_url:
                await asyncio.sleep(3)
                stream_url = await fetch_stream(yt_url, video=want_video)

        else:
            vid = extract_video_id(link) if link != "__search__" else None

            if vid:
                # YouTube URL — exact
                yt_url = self.base + vid
                stream_url = await fetch_stream(yt_url, video=want_video)
                if not stream_url:
                    await asyncio.sleep(3)
                    stream_url = await fetch_stream(yt_url, video=want_video)

            else:
                # Plain text query or __search__ dummy
                # Use yt-dlp search with cookies to resolve to a URL first
                search_query = link if link != "__search__" else link
                print(f"DOWNLOAD: yt-dlp search for: {search_query[:60]}")

                meta = await search_with_ytdlp(search_query)
                if meta:
                    yt_url = self.base + meta["vidid"]
                    print(f"DOWNLOAD: resolved to {yt_url}")
                    stream_url = await fetch_stream(yt_url, video=want_video)
                    if not stream_url:
                        await asyncio.sleep(3)
                        stream_url = await fetch_stream(yt_url, video=want_video)
                else:
                    # yt-dlp search also failed — last resort: send raw text to backend
                    print(f"DOWNLOAD: yt-dlp search failed, sending raw text to backend")
                    stream_url = await fetch_stream(search_query, video=want_video)
                    if not stream_url:
                        await asyncio.sleep(3)
                        stream_url = await fetch_stream(search_query, video=want_video)

        if stream_url:
            return stream_url, True

        raise Exception(
            f"API returned no {'video' if want_video else 'audio'} stream for: {link}"
        )

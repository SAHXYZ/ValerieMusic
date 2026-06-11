import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall, TelegramServerError
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from pytgcalls.types.stream import StreamAudioEnded

import config
from ValerieMusic import LOGGER, YouTube, app
from ValerieMusic.misc import db
from ValerieMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from ValerieMusic.utils.exceptions import AssistantErr
from ValerieMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from ValerieMusic.utils.inline.play import stream_markup
from ValerieMusic.utils.stream.autoclear import auto_clean
from ValerieMusic.utils.thumbnails import gen_thumb
from strings import get_string


autoend = {}
counter = {}


async def _clear_(chat_id: int):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


# ──────────────────────────────────────────────────────────────
# _make_stream — build pytgcalls stream object
#
# For remote URLs (googlevideo): add reconnect flags so ffmpeg
# automatically recovers from transient network drops.
# For local files: no reconnect flags needed.
# ──────────────────────────────────────────────────────────────
def _make_stream(
    link: str,
    video: bool = False,
    seek_to: str = None,
    duration: str = None,
):
    is_remote = isinstance(link, str) and link.startswith("http")
    reconnect = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5" if is_remote else ""

    if video:
        parts = [reconnect] if reconnect else []
        if seek_to and duration:
            parts.append(f"-ss {seek_to} -to {duration}")
        extra = " ".join(parts).strip() or None
        kwargs = {"additional_ffmpeg_parameters": extra} if extra else {}
        return AudioVideoPiped(
            link,
            audio_parameters=HighQualityAudio(),
            video_parameters=MediumQualityVideo(),
            **kwargs,
        )
    else:
        parts = []
        if reconnect:
            parts.append(reconnect)
        parts.append("-vn")
        if seek_to and duration:
            parts.append(f"-ss {seek_to} -to {duration}")
        extra = " ".join(parts).strip() or None
        kwargs = {"additional_ffmpeg_parameters": extra} if extra else {}
        return AudioPiped(
            link,
            audio_parameters=HighQualityAudio(),
            **kwargs,
        )


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            "ValerieAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = Client(
            "ValerieAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)

        self.userbot3 = Client(
            "ValerieAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = Client(
            "ValerieAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = Client(
            "ValerieAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)

    # ── basic controls ──────────────────────────────────────────
    async def pause_stream(self, chat_id: int):
        (await group_assistant(self, chat_id)).pause_stream(chat_id)

    async def resume_stream(self, chat_id: int):
        (await group_assistant(self, chat_id)).resume_stream(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_group_call(chat_id)
        except:
            pass

    async def stop_stream_force(self, chat_id: int):
        for client in (getattr(self, n) for n in ("one", "two", "three", "four", "five")):
            try:
                await client.leave_group_call(chat_id)
            except:
                pass
        await _clear_(chat_id)

    async def force_stop_stream(self, chat_id: int):
        """Stop current stream and clear state. Used for forceplay."""
        try:
            assistant = await group_assistant(self, chat_id)
            await assistant.leave_group_call(chat_id)
        except Exception as e:
            print(f"force_stop_stream: leave_group_call skipped ({e})")
        finally:
            await _clear_(chat_id)

    async def stream_call(self, link: str):
        """Validate stream URL before joining. Used for M3U8/index links."""
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(link, allow_redirects=True) as resp:
                    if resp.status >= 400:
                        raise Exception(f"Stream URL returned HTTP {resp.status}")
        except aiohttp.ClientError as e:
            raise Exception(f"Stream URL unreachable: {e}")

    # ── join_call ────────────────────────────────────────────────
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        _ = get_string(await get_lang(chat_id))

        stream = _make_stream(link, video=bool(video))

        try:
            await assistant.join_group_call(
                chat_id, stream, stream_type=StreamType().pulse_stream
            )
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(_["call_9"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    # ── seek_stream ─────────────────────────────────────────────
    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        stream = _make_stream(
            file_path,
            video=(mode == "video"),
            seek_to=to_seek,
            duration=duration,
        )
        await assistant.change_stream(chat_id, stream)

    # ── speedup_stream ──────────────────────────────────────────
    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            os.makedirs(chatdir, exist_ok=True)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}.get(str(speed), 1.0)
                proc = await asyncio.create_subprocess_shell(
                    f'ffmpeg -i "{file_path}" -filter:v setpts={vs}*PTS -filter:a atempo={speed} "{out}"',
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path

        dur = int(
            await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        )
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        stream = _make_stream(
            out,
            video=(playing[0]["streamtype"] == "video"),
            seek_to=played,
            duration=duration,
        )
        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    # ── skip_stream ─────────────────────────────────────────────
    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = _make_stream(link, video=bool(video))
        await assistant.change_stream(chat_id, stream)

    # ── change_stream ────────────────────────────────────────────
    # Called automatically when a song ends (StreamAudioEnded event).
    #
    # Queue items are always stored as "vid_{vidid}" so this always
    # calls YouTube.download() to get a fresh stream URL — never reuses
    # expired googlevideo URLs.
    # ─────────────────────────────────────────────────────────────
    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        loop = await get_loop(chat_id)

        popped = None
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                await set_loop(chat_id, loop - 1)

            if popped:
                await auto_clean(popped)

            if not check:
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except Exception as e:
                    print(f"leave_group_call error: {e}")
                return

        except Exception as e:
            print(f"change_stream queue error: {e}")
            try:
                await _clear_(chat_id)
                await client.leave_group_call(chat_id)
            except:
                pass
            return

        queued           = check[0]["file"]
        language         = await get_lang(chat_id)
        _                = get_string(language)
        title            = (check[0]["title"]).title()
        user             = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype       = check[0]["streamtype"]
        videoid          = check[0]["vidid"]
        db[chat_id][0]["played"] = 0

        video = True if str(streamtype) == "video" else False

        # ── LIVE ────────────────────────────────────────────────
        if queued and isinstance(queued, str) and "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await app.send_message(original_chat_id, text=_["call_6"])
            stream = _make_stream(link, video=video)
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            img = await gen_thumb(videoid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title, check[0]["dur"], user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        # ── YouTube vid_ ─────────────────────────────────────────
        elif queued and isinstance(queued, str) and "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                file_path, direct = await YouTube.download(
                    videoid, mystic, videoid=True, video=video
                )
            except Exception as e:
                print(f"change_stream download error for {videoid}: {e}")
                return await mystic.edit_text(
                    f"{_['call_6']}\n\n<code>{e}</code>",
                    disable_web_page_preview=True,
                )

            if not file_path:
                return await mystic.edit_text(_["call_6"])

            stream = _make_stream(file_path, video=video)
            try:
                await client.change_stream(chat_id, stream)
            except Exception as e:
                print(f"client.change_stream error: {e}")
                return await app.send_message(original_chat_id, text=_["call_6"])

            await mystic.delete()
            img = await gen_thumb(videoid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title, check[0]["dur"], user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

        # ── Index / M3U8 ─────────────────────────────────────────
        elif queued and isinstance(queued, str) and "index_" in queued:
            src = videoid
            stream = _make_stream(src, video=video)
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        # ── Telegram / SoundCloud / local file ───────────────────
        else:
            src = queued
            stream = _make_stream(src, video=video)
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])

            if videoid == "telegram":
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=(
                        config.TELEGRAM_AUDIO_URL
                        if str(streamtype) == "audio"
                        else config.TELEGRAM_VIDEO_URL
                    ),
                    caption=_["stream_1"].format(
                        config.SUPPORT_GROUP, title, check[0]["dur"], user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif videoid == "soundcloud":
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.SOUNCLOUD_IMG_URL,
                    caption=_["stream_1"].format(
                        config.SUPPORT_GROUP, title, check[0]["dur"], user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                img = await gen_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title, check[0]["dur"], user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    # ── ping / start / event hooks ───────────────────────────────
    async def ping(self):
        p = []
        if config.STRING1:
            p.append(await self.one.ping)
        if config.STRING2:
            p.append(await self.two.ping)
        if config.STRING3:
            p.append(await self.three.ping)
        if config.STRING4:
            p.append(await self.four.ping)
        if config.STRING5:
            p.append(await self.five.ping)
        if not p:
            return "0"
        return str(round(sum(p) / len(p), 3))

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def _on_end(client, update: Update):
            if isinstance(update, StreamAudioEnded):
                await self.change_stream(client, update.chat_id)


Valerie = Call()

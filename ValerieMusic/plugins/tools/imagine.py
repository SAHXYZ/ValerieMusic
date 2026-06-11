import asyncio
import io
import os
import re
import tempfile
import time
import urllib.parse

import aiohttp
from pyrogram import filters

from ValerieMusic import app
from config import BANNED_USERS

SEP = "━" * 20
_cd: dict = {}
COOL = 8  # seconds between generations per chat

SIZES = {
    "-hd": (1280, 720),
    "-wide": (1920, 1080),
    "-square": (1024, 1024),
    "-tall": (720, 1280),
    "-portrait": (832, 1216),
    "-landscape": (1216, 832),
}

USAGE = (
    f"🎨 <b>Image Generation</b>\n{SEP}\n"
    "<code>/imagine a sunset over mountains</code>\n"
    "<code>/imagine anime girl -hd</code>\n"
    "<code>/imagine dragon -seed 42</code>\n\n"
    "<b>Size:</b> <code>-square</code> <code>-hd</code> <code>-wide</code> "
    "<code>-tall</code> <code>-portrait</code> <code>-landscape</code>\n"
    "<b>Flags:</b> <code>-seed N</code> <code>-nologo</code>\n\n"
    "<i>Provider: Valerie AI</i>"
)

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "image/webp,image/jpeg,image/*,*/*",
}

_STOP = {
    "a", "an", "the", "in", "on", "at", "of", "for", "to", "and", "or", "with",
    "is", "are", "was", "were", "by", "from", "as", "i", "my", "me", "you",
}

# Internal model list — never exposed to users
_MODELS = ["flux", "flux-schnell", "flux-realism", "any-dark"]


def _smart_filename(prompt: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9 ]", " ", prompt.lower())
    words = [w for w in clean.split() if w and w not in _STOP]
    return "".join(w.capitalize() for w in words[:4] or ["image"]) + ".jpg"


def _parse(raw: str):
    text = re.sub(r"^[\/!.]imagine\s*", "", raw, flags=re.IGNORECASE).strip()
    w, h = 1024, 1024
    seed = None
    nologo = False
    for flag, (fw, fh) in SIZES.items():
        if flag in text:
            w, h = fw, fh
            text = text.replace(flag, "").strip()
    m = re.search(r"-seed\s+(\d+)", text)
    if m:
        seed = int(m.group(1))
        text = text.replace(m.group(0), "").strip()
    if "-nologo" in text:
        nologo = True
        text = text.replace("-nologo", "").strip()
    return text.strip(), w, h, seed, nologo


def _to_jpeg(raw_bytes: bytes) -> bytes:
    if raw_bytes[:2] == b"\xff\xd8" and len(raw_bytes) > 10000:
        return raw_bytes
    try:
        from PIL import Image, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        for suffix in (".jpg", ".webp", ".png", ".gif"):
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                    f.write(raw_bytes)
                    tmp = f.name
                img = Image.open(tmp)
                img.load()
                if img.mode in ("RGBA", "LA", "P"):
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
                    bg.paste(img, mask=mask)
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=92, optimize=True)
                result = out.getvalue()
                if len(result) > 5000:
                    return result
            except Exception:
                pass
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
    except Exception as e:
        print(f"[imagine] _to_jpeg: {e}")
    return raw_bytes


async def _fetch(url: str, timeout: int = 90) -> "bytes | None":
    try:
        async with aiohttp.ClientSession(headers=HDRS) as s:
            async with s.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
            ) as r:
                if r.status != 200:
                    return None
                data = b""
                async for chunk in r.content.iter_chunked(65536):
                    data += chunk
                    if len(data) > 5 and data[:5].lower() in (b"<!doc", b"<html"):
                        return None
                if len(data) < 20000:
                    return None
                return data
    except asyncio.TimeoutError:
        print(f"[imagine] timeout: {url[:60]}")
    except Exception as e:
        print(f"[imagine] fetch error: {e}")
    return None


async def _pollinations(prompt, w, h, model, seed, nologo) -> "bytes | None":
    enc = urllib.parse.quote(prompt)
    params = {"width": w, "height": h, "model": model, "noCache": "true"}
    if seed is not None:
        params["seed"] = seed
    if nologo:
        params["nologo"] = "true"
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return await _fetch(f"https://image.pollinations.ai/prompt/{enc}?{q}", timeout=90)


async def _generate(prompt, w, h, seed, nologo, status_msg=None):
    short = prompt[:50] + ("…" if len(prompt) > 50 else "")

    async def update(text):
        if status_msg:
            try:
                await status_msg.edit_text(
                    f"🎨 <b>Generating…</b>\n{SEP}\n"
                    f"◆ {text}\n◆ Prompt → <code>{short}</code>"
                )
            except Exception:
                pass

    for model in _MODELS:
        await update("Provider → <code>Valerie AI</code>")
        data = await _pollinations(prompt, w, h, model, seed, nologo)
        if data:
            return _to_jpeg(data), "Valerie AI"
        await asyncio.sleep(2)

    return None, ""


@app.on_message(filters.command(["imagine", "imaginehelp"]) & ~BANNED_USERS)
async def cmd_imagine(client, message):
    if message.command and message.command[0] == "imaginehelp":
        return await message.reply_text(USAGE)

    now = time.time()
    wait = COOL - (now - _cd.get(message.chat.id, 0))
    if wait > 0:
        return await message.reply_text(f"⏳ <i>Wait <code>{wait:.0f}s</code>.</i>")

    prompt, w, h, seed, nologo = _parse(message.text or "")
    if not prompt:
        return await message.reply_text(USAGE)

    _cd[message.chat.id] = now
    short = prompt[:60] + ("…" if len(prompt) > 60 else "")

    msg = await message.reply_text(
        f"🎨 <b>Generating…</b>\n{SEP}\n"
        f"◆ Prompt → <code>{short}</code>\n"
        f"◆ Size   → <code>{w}×{h}</code>"
    )

    img, provider = await _generate(prompt, w, h, seed, nologo, msg)
    if not img:
        _cd.pop(message.chat.id, None)
        return await msg.edit_text(
            f"❌ <b>All providers failed</b>\n{SEP}\n"
            "<i>Valerie AI tried all engines and failed. Try again shortly.</i>"
        )

    fname = _smart_filename(prompt)
    cap = (
        f"🎨 <b>Generated Image</b>\n{SEP}\n"
        f"◆ Prompt   → <code>{short}</code>\n"
        f"◆ Size     → <code>{w}×{h}</code>\n"
        f"◆ Provider → <code>{provider}</code>"
        + (f"\n◆ Seed     → <code>{seed}</code>" if seed is not None else "")
    )

    for as_doc in (False, True):
        buf = io.BytesIO(img)
        buf.name = fname
        buf.seek(0)
        try:
            kwargs = {"caption": cap, "reply_to_message_id": message.id}
            if as_doc:
                await app.send_document(message.chat.id, buf, **kwargs)
            else:
                await app.send_photo(message.chat.id, buf, **kwargs)
            await msg.delete()
            return
        except Exception as e:
            if as_doc:
                await msg.edit_text(f"❌ <b>Upload failed:</b> <code>{e}</code>")
            else:
                print(f"[imagine] photo send failed: {e}")

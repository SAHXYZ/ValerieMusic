# ValerieMusic — Sticker Tools (ported from ValerieBot userbot)
# Public: /sticker /unsticker /stickid /mmf  — usable by everyone.

import io
import os
import re
import subprocess
import tempfile

from pyrogram import filters

from ValerieMusic import app
from config import BANNED_USERS

SEP = "━" * 20
FONT_BASE = "/usr/share/fonts"

# Curated short aliases (preferred names users will reach for).
_ALIAS_FONTS = {
    "regular": f"{FONT_BASE}/truetype/dejavu/DejaVuSans.ttf",
    "bold": f"{FONT_BASE}/truetype/dejavu/DejaVuSans-Bold.ttf",
    "italic": f"{FONT_BASE}/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "bolditalic": f"{FONT_BASE}/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    "mono": f"{FONT_BASE}/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "serif": f"{FONT_BASE}/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "serifitalic": f"{FONT_BASE}/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
    "condensed": f"{FONT_BASE}/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "liberation": f"{FONT_BASE}/truetype/liberation/LiberationSans-Bold.ttf",
    "free": f"{FONT_BASE}/truetype/freefont/FreeSansBold.ttf",
    "caladea": f"{FONT_BASE}/truetype/crosextra/Caladea-Bold.ttf",
    "carlito": f"{FONT_BASE}/truetype/crosextra/Carlito-Bold.ttf",
}

# Also bundle the fonts shipped with the bot (ValerieMusic/assets/*.ttf).
_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")
for _alias, _fname in (("valerie", "font.ttf"), ("valerie2", "font2.ttf"), ("valerie3", "font3.ttf")):
    _p = os.path.join(_ASSET_DIR, _fname)
    if os.path.exists(_p):
        _ALIAS_FONTS[_alias] = _p


def _discover_fonts() -> dict:
    """
    Build the full font catalogue.

    1. Curated aliases first (bold, italic, mono, serif, caladea …).
    2. Every .ttf / .otf installed under /usr/share/fonts, keyed by its file
       name stem (lowercased, alphanumeric only) — so users can pick ANY font
       installed on the system by its name, e.g. `poppinsbold`, `notoserif`.
    """
    fonts = {k: v for k, v in _ALIAS_FONTS.items() if os.path.exists(v)}
    try:
        for root, _dirs, files in os.walk(FONT_BASE):
            for fn in files:
                if fn.lower().endswith((".ttf", ".otf")):
                    stem = os.path.splitext(fn)[0]
                    key = re.sub(r"[^a-z0-9]", "", stem.lower())
                    if key and key not in fonts:
                        fonts[key] = os.path.join(root, fn)
    except Exception:
        pass
    return fonts


FONTS = _discover_fonts()
# Guaranteed fallback so the plugin never crashes if nothing is installed.
DEFAULT_FONT = FONTS.get("bold") or (next(iter(FONTS.values())) if FONTS else None)

EMOJI_COLOURS = {
    "❤️": (255, 59, 48), "🔴": (255, 59, 48), "🟠": (255, 149, 0),
    "🟡": (255, 214, 0), "⭐": (255, 214, 0), "✨": (255, 215, 0),
    "💛": (255, 214, 0), "💚": (52, 199, 89), "🟢": (52, 199, 89),
    "🌸": (255, 105, 180), "💙": (0, 122, 255), "🔵": (0, 122, 255),
    "💜": (175, 82, 222), "🟣": (175, 82, 222), "🌹": (255, 45, 85),
    "💖": (255, 105, 180), "🤍": (255, 255, 255), "⬜": (255, 255, 255),
    "⬛": (28, 28, 30), "🖤": (28, 28, 30), "🔥": (255, 69, 0),
    "⚡": (255, 220, 0), "🎨": (175, 82, 222), "💎": (100, 200, 255),
    "👑": (255, 215, 0), "🩷": (255, 105, 180), "🧡": (255, 149, 0),
}

NAMED_COLOURS = {
    "red": (255, 59, 48), "orange": (255, 149, 0), "yellow": (255, 214, 0),
    "green": (52, 199, 89), "blue": (0, 122, 255), "purple": (175, 82, 222),
    "pink": (255, 105, 180), "white": (255, 255, 255), "black": (28, 28, 30),
    "gold": (255, 215, 0), "silver": (192, 192, 192), "cyan": (0, 199, 190),
    "magenta": (255, 45, 85), "violet": (130, 80, 220), "teal": (0, 164, 154),
    "maroon": (128, 0, 0), "navy": (0, 0, 128), "lime": (0, 255, 0),
    "coral": (255, 100, 80), "crimson": (220, 20, 60), "indigo": (75, 0, 130),
    "brown": (139, 69, 19), "aqua": (0, 255, 255),
}

POSITIONS = {
    "center": "center", "top": "top", "bottom": "bottom", "left": "left",
    "right": "right", "topleft": "topleft", "topright": "topright",
    "bottomleft": "bottomleft", "bottomright": "bottomright",
    "topcenter": "top", "bottomcenter": "bottom",
}

USAGE = (
    f"✍️ <b>MMF — Text on Sticker</b>\n{SEP}\n"
    "<code>/mmf \"text\" [position] [size] [font] [colour/emoji]</code>\n\n"
    "<b>Text</b> goes in double quotes.\n\n"
    "<b>Colours</b> — any of these (mix freely):\n"
    "• emoji: <code>🔴 🟠 🟡 🟢 🔵 🟣</code>\n"
    "• name: <code>red</code> <code>crimson</code> <code>rebeccapurple</code> "
    "<code>gold</code> … (every CSS colour name)\n"
    "• hex: <code>#FF6B6B</code>\n"
    "• functional: <code>rgb(255,0,0)</code> <code>hsl(200,80%,50%)</code>\n"
    "• two or more = gradient (left→right)\n\n"
    "<b>Size:</b> <code>-size 90</code> or words "
    "<code>tiny small medium big large huge giant max</code>\n"
    "<b>Position:</b> <code>top center bottom left right "
    "topleft topright bottomleft bottomright</code>\n"
    "<b>Font:</b> <code>bold italic mono serif caladea carlito</code> "
    "— or any installed font by name (see <code>/mmfhelp</code>)\n\n"
    "<b>Examples:</b>\n"
    "<code>/mmf \"Hello\" white</code>\n"
    "<code>/mmf \"FIRE\" bottom huge bold 🔴 🟠 🟡</code>\n"
    "<code>/mmf \"Valerie\" center -size 120 serif #FF6B6B #FFE66D</code>\n\n"
    "<i>Reply to any image / sticker / webp / webm / mp4, then use /mmf.</i>"
)


def extract_emojis_from_str(text: str) -> list:
    result, i, chars = [], 0, list(text)
    while i < len(chars):
        cp = ord(chars[i])
        if (0x1F300 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF
                or cp in (0x2B50, 0x2B55, 0x2764, 0x2665, 0x2666, 0x2714)):
            e, j = chars[i], i + 1
            while j < len(chars) and ord(chars[j]) in (
                *range(0xFE00, 0xFE10), 0x200D, *range(0x1F3FB, 0x1F400)
            ):
                e += chars[j]; j += 1
            result.append(e); i = j
        else:
            i += 1
    return result


def parse_colours(tokens: list) -> list:
    """
    Resolve every token to an (R,G,B) colour. Supports, in order:
      • emoji shortcuts (🔴 🟢 …)
      • any CSS/X11 colour name (red, rebeccapurple, lightgoldenrodyellow, …)
      • hex (#rgb / #rrggbb / #rrggbbaa)
      • rgb(...)  /  rgba(...)  /  hsl(...)  /  hsv(...)
    All name/hex/functional forms are handled by PIL's ImageColor engine, so
    literally every colour PIL knows is accepted.
    """
    from PIL import ImageColor

    colours = []
    for tok in tokens:
        emojis = extract_emojis_from_str(tok)
        if emojis:
            for em in emojis:
                c = EMOJI_COLOURS.get(em)
                if c:
                    colours.append(c)
            continue
        # Try PIL's full colour parser (names, hex, rgb(), hsl(), …).
        try:
            rgb = ImageColor.getrgb(tok)
            colours.append(rgb[:3])
            continue
        except Exception:
            pass
        # Last resort: a few extra named colours PIL might miss.
        if tok.lower() in NAMED_COLOURS:
            colours.append(NAMED_COLOURS[tok.lower()])
    return colours if colours else [(255, 255, 255)]


SIZE_WORDS = {
    "tiny": 36, "small": 52, "medium": 72, "normal": 72,
    "big": 96, "large": 110, "huge": 140, "giant": 180, "max": 240,
}


def parse_mmf_args(raw: str) -> dict:
    text = re.sub(r"^[\/!.]mmf\s*", "", raw, flags=re.IGNORECASE).strip()
    if not text:
        return {}
    m = re.match(r'^"([^"]+)"(.*)$', text)
    if not m:
        return {}
    final_text = m.group(1).strip()
    rest = m.group(2).strip()

    # Explicit size: -size N  (e.g. -size 90). Clamped to a sane range.
    size = None
    sm = re.search(r"-size\s+(\d+)", rest)
    if sm:
        size = max(12, min(int(sm.group(1)), 320))
        rest = rest.replace(sm.group(0), "").strip()

    position, font_key, colour_tokens = "bottom", "bold", []
    for tok in rest.split():
        tl = tok.lower()
        if tl in POSITIONS:
            position = POSITIONS[tl]
        elif tl in SIZE_WORDS and size is None:
            size = SIZE_WORDS[tl]
        elif tl in FONTS:
            font_key = tl
        else:
            colour_tokens.append(tok)

    colours = parse_colours(colour_tokens) if colour_tokens else [(255, 255, 255)]
    return {
        "text": final_text,
        "position": position,
        "font_key": font_key,
        "colours": colours,
        "size": size,
    }


def make_gradient_text(draw, text, font, colours, x, y, img_width, shadow=True):
    if shadow:
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 160))
    if len(colours) == 1:
        draw.text((x, y), text, font=font, fill=(*colours[0], 255))
        return
    cx, n = x, len(text)
    for i, ch in enumerate(text):
        try:
            cb = font.getbbox(ch); cw = cb[2] - cb[0]
        except Exception:
            cw = 30
        t = i / max(n - 1, 1)
        num_stops = len(colours)
        seg = t * (num_stops - 1)
        seg_idx = min(int(seg), num_stops - 2)
        seg_t = seg - seg_idx
        c1, c2 = colours[seg_idx], colours[seg_idx + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * seg_t)
        g = int(c1[1] + (c2[1] - c1[1]) * seg_t)
        b = int(c1[2] + (c2[2] - c1[2]) * seg_t)
        draw.text((cx, y), ch, font=font, fill=(r, g, b, 255))
        cx += cw


def calc_position(position, tw, th, img_w, img_h, margin=30):
    cx, cy = (img_w - tw) // 2, (img_h - th) // 2
    pos_map = {
        "center": (cx, cy), "top": (cx, margin),
        "bottom": (cx, img_h - th - margin), "left": (margin, cy),
        "right": (img_w - tw - margin, cy), "topleft": (margin, margin),
        "topright": (img_w - tw - margin, margin),
        "bottomleft": (margin, img_h - th - margin),
        "bottomright": (img_w - tw - margin, img_h - th - margin),
    }
    return pos_map.get(position, (cx, img_h - th - margin))


def compose_mmf(img_bytes, text, position, font_key, colours, size=None) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA").resize((512, 512), Image.LANCZOS)
    draw = ImageDraw.Draw(img, "RGBA")
    font_path = FONTS.get(font_key, DEFAULT_FONT)
    font = None

    if size:
        # Explicit user size — use it directly (no auto-shrink).
        try:
            font = ImageFont.truetype(font_path, int(size))
        except Exception:
            font = None
        if font is not None:
            try:
                bbox = font.getbbox(text)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = len(text) * size // 2, size
    if font is None:
        # Auto-fit: shrink until the text fits within the sticker width.
        for s in range(72, 20, -4):
            try:
                font = ImageFont.truetype(font_path, s)
                bbox = font.getbbox(text)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if tw <= 480:
                    break
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()
            tw, th = len(text) * 10, 20
        else:
            try:
                bbox = font.getbbox(text)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = len(text) * 36, 72

    x, y = calc_position(position, tw, th, 512, 512)
    outline_colour = (0, 0, 0, 200) if sum(colours[0]) > 380 else (255, 255, 255, 200)
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_colour)
    make_gradient_text(draw, text, font, colours, x, y, 512, shadow=True)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=90)
    return out.getvalue()


async def _download_bytes(msg) -> "bytes | None":
    try:
        bio = await msg.download(in_memory=True)
        if bio is None:
            return None
        return bytes(bio.getbuffer())
    except Exception:
        path = await msg.download()
        if not path:
            return None
        with open(path, "rb") as f:
            data = f.read()
        try:
            os.remove(path)
        except Exception:
            pass
        return data


@app.on_message(filters.command(["sticker", "kk"]) & ~BANNED_USERS)
async def cmd_sticker(client, message):
    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.sticker or reply.document):
        return await message.reply_text("❌ <i>Reply to an image or sticker.</i>")
    msg = await message.reply_text("🎨 <i>Converting to sticker…</i>")
    try:
        from PIL import Image
        data = await _download_bytes(reply)
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.thumbnail((512, 512), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP")
        buf.name = "sticker.webp"
        buf.seek(0)
        await app.send_sticker(message.chat.id, buf, reply_to_message_id=reply.id)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ <code>{e}</code>")


@app.on_message(filters.command(["unsticker", "stickerimage"]) & ~BANNED_USERS)
async def cmd_unsticker(client, message):
    reply = message.reply_to_message
    if not reply or not reply.sticker:
        return await message.reply_text("❌ <i>Reply to a sticker.</i>")
    msg = await message.reply_text("🖼 <i>Converting sticker to image…</i>")
    try:
        from PIL import Image
        data = await _download_bytes(reply)
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.name = "sticker.png"
        buf.seek(0)
        await app.send_document(message.chat.id, buf, reply_to_message_id=reply.id)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ <code>{e}</code>")


@app.on_message(filters.command(["stickid", "stickerid"]) & ~BANNED_USERS)
async def cmd_stickid(client, message):
    reply = message.reply_to_message
    if not reply or not reply.sticker:
        return await message.reply_text("❌ <i>Reply to a sticker.</i>")
    st = reply.sticker
    await message.reply_text(
        f"🎭 <b>Sticker Info</b>\n{SEP}\n"
        f"◆ Emoji   → <code>{st.emoji or '❓'}</code>\n"
        f"◆ Set     → <code>{st.set_name or 'N/A'}</code>\n"
        f"◆ File ID → <code>{st.file_id}</code>\n"
        f"◆ Size    → <code>{(st.file_size or 0) // 1024}</code> KB"
    )


@app.on_message(filters.command(["mmf", "mmfhelp"]) & ~BANNED_USERS)
async def cmd_mmf(client, message):
    if message.command and message.command[0] == "mmfhelp":
        curated = [k for k in _ALIAS_FONTS if k in FONTS]
        fonts_available = ", ".join(f"<code>{k}</code>" for k in sorted(curated))
        extra = max(len(FONTS) - len(curated), 0)
        return await message.reply_text(
            f"{USAGE}\n\n<b>Quick fonts:</b>\n{fonts_available}\n\n"
            f"<i>+ {extra} more installed fonts — type any font's name "
            f"(lowercase, no spaces), e.g. <code>notoserif</code>.</i>"
        )

    args = parse_mmf_args(message.text or "")
    if not args or not args.get("text"):
        return await message.reply_text(USAGE)

    reply = message.reply_to_message
    if not reply or not (reply.photo or reply.sticker or reply.document
                         or reply.video or reply.animation):
        return await message.reply_text(
            "❌ <i>Reply to any media (image / sticker / webp / webm / mp4) first.</i>\n\n" + USAGE
        )

    msg = await message.reply_text("✍️ <i>Preparing media…</i>")
    tmp_in = tmp_frm = None
    try:
        from PIL import Image
        raw_data = await _download_bytes(reply)
        if not raw_data:
            return await msg.edit_text("❌ <i>Could not download media.</i>")

        mime = ""
        if reply.video and reply.video.mime_type:
            mime = reply.video.mime_type
        elif reply.animation and reply.animation.mime_type:
            mime = reply.animation.mime_type
        elif reply.document and reply.document.mime_type:
            mime = reply.document.mime_type
        if not mime:
            if raw_data[:4] == b"\x1a\x45\xdf\xa3":
                mime = "video/webm"
            elif raw_data[4:8] == b"ftyp":
                mime = "video/mp4"
            elif raw_data[:6] in (b"GIF87a", b"GIF89a"):
                mime = "image/gif"
            elif raw_data[:4] == b"RIFF" and raw_data[8:12] == b"WEBP":
                mime = "image/webp"

        is_video = mime.startswith("video/") or mime == "image/gif" or bool(reply.video or reply.animation)

        if is_video:
            await msg.edit_text("✍️ <i>Extracting frame from video…</i>")
            ext = ".mp4" if "mp4" in mime else ".webm"
            tmp_in = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp_in.write(raw_data); tmp_in.flush(); tmp_in.close()
            tmp_frm = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_frm.close()
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_in.name, "-vframes", "1", "-q:v", "2", tmp_frm.name],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0 or not os.path.getsize(tmp_frm.name):
                return await msg.edit_text(
                    "❌ <i>ffmpeg failed to extract frame. Is ffmpeg installed?</i>"
                )
            with open(tmp_frm.name, "rb") as f:
                raw_data = f.read()
        elif mime == "image/webp":
            try:
                img_check = Image.open(io.BytesIO(raw_data))
                img_check.seek(0)
                out_buf = io.BytesIO()
                img_check.convert("RGBA").save(out_buf, format="PNG")
                raw_data = out_buf.getvalue()
            except Exception:
                pass

        await msg.edit_text("✍️ <i>Composing text…</i>")
        sticker_bytes = compose_mmf(
            raw_data, args["text"], args["position"], args["font_key"],
            args["colours"], args.get("size"),
        )
        buf = io.BytesIO(sticker_bytes)
        buf.name = "mmf.webp"
        buf.seek(0)
        await app.send_sticker(message.chat.id, buf, reply_to_message_id=reply.id)
        await msg.delete()
    except subprocess.TimeoutExpired:
        await msg.edit_text("❌ <i>ffmpeg timed out (video too long?)</i>")
    except FileNotFoundError:
        await msg.edit_text("❌ <i>ffmpeg not found. Install it: apt install ffmpeg</i>")
    except Exception as e:
        await msg.edit_text(f"❌ <code>{e}</code>")
    finally:
        for p in (tmp_in, tmp_frm):
            try:
                if p and os.path.exists(p.name):
                    os.unlink(p.name)
            except Exception:
                pass

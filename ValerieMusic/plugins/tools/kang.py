# ValerieMusic — Kang / Sticker Pack (ported & rebuilt from ValerieBot userbot)
#
# Public: anyone can /kang a replied sticker / image / video into THEIR OWN pack
# (owned by the requesting user; the bot just builds it). Auto-creates a new pack
# when one fills up. Supports static, video and animated (.tgs) stickers.
#
# Commands:
#   /kang [emoji]   — add the replied media to your pack
#   /mypacks        — list your packs
#
# NOTE: the requesting user must have started the bot in DM at least once,
#       otherwise Telegram refuses to create a sticker set for them.

import io
import os
import subprocess
import tempfile

from pyrogram import filters, raw
from pyrogram.errors import RPCError, StickersetInvalid

from ValerieMusic import app
from ValerieMusic.core.mongo import mongodb
from config import BANNED_USERS

SEP = "━" * 20
MAX_PER_PACK = 120  # Telegram limit per sticker set
packsdb = mongodb.stickerpacks


# ── media preparation ───────────────────────────────────────────────────────

async def _download_bytes(msg) -> "bytes | None":
    try:
        bio = await msg.download(in_memory=True)
        if bio is not None:
            return bytes(bio.getbuffer())
    except Exception:
        pass
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


def _detect_type(reply, data: bytes) -> str:
    """Returns 'static' | 'video' | 'animated'."""
    if reply.sticker:
        if reply.sticker.is_animated:
            return "animated"
        if reply.sticker.is_video:
            return "video"
        return "static"
    if reply.animation or reply.video:
        return "video"
    if data[:2] == b"\x1f\x8b":  # gzip → .tgs
        return "animated"
    if data[:4] == b"\x1a\x45\xdf\xa3" or data[4:8] == b"ftyp":
        return "video"
    return "static"


def _prepare_static(data: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    img.thumbnail((512, 512), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _prepare_video(data: bytes) -> bytes:
    tmp_in = tmp_out = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(data)
            tmp_in = f.name
        tmp_out = tmp_in + "_out.webm"
        r = subprocess.run([
            "ffmpeg", "-y", "-i", tmp_in, "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,"
                   "pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0",
            "-c:v", "libvpx-vp9", "-b:v", "400k", "-an", "-pix_fmt", "yuva420p",
            tmp_out,
        ], capture_output=True, timeout=40)
        if r.returncode == 0 and os.path.exists(tmp_out):
            with open(tmp_out, "rb") as f:
                out = f.read()
            if len(out) > 1000:
                return out
    except Exception as e:
        print(f"[kang] video prep error: {e}")
    finally:
        for p in (tmp_in, tmp_out):
            if p and os.path.exists(p):
                os.unlink(p)
    return data


# ── raw sticker-set helpers ─────────────────────────────────────────────────

async def _upload_document(data: bytes, stype: str):
    """Upload the prepared file and return a raw InputDocument."""
    mime = {"video": "video/webm", "animated": "application/x-tgsticker"}.get(stype, "image/png")
    fname = {"video": "sticker.webm", "animated": "sticker.tgs"}.get(stype, "sticker.png")

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix="_" + fname, delete=False) as f:
            f.write(data)
            tmp = f.name
        uploaded = await app.save_file(tmp)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)

    media = await app.invoke(
        raw.functions.messages.UploadMedia(
            peer=raw.types.InputPeerSelf(),
            media=raw.types.InputMediaUploadedDocument(
                file=uploaded,
                mime_type=mime,
                attributes=[raw.types.DocumentAttributeFilename(file_name=fname)],
            ),
        )
    )
    doc = media.document
    return raw.types.InputDocument(
        id=doc.id, access_hash=doc.access_hash, file_reference=doc.file_reference
    )


async def _input_user(user_id: int):
    peer = await app.resolve_peer(user_id)
    return raw.types.InputUser(user_id=peer.user_id, access_hash=peer.access_hash)


async def _add_to_set(short: str, input_doc, emoji: str):
    await app.invoke(
        raw.functions.stickers.AddStickerToSet(
            stickerset=raw.types.InputStickerSetShortName(short_name=short),
            sticker=raw.types.InputStickerSetItem(document=input_doc, emoji=emoji),
        )
    )


async def _create_set(user_id: int, short: str, title: str, input_doc, emoji: str, stype: str):
    kwargs = {}
    if stype == "video":
        kwargs["videos"] = True
    elif stype == "animated":
        kwargs["animated"] = True
    await app.invoke(
        raw.functions.stickers.CreateStickerSet(
            user_id=await _input_user(user_id),
            title=title[:64],
            short_name=short,
            stickers=[raw.types.InputStickerSetItem(document=input_doc, emoji=emoji)],
            **kwargs,
        )
    )


# ── pack bookkeeping (mongodb) ──────────────────────────────────────────────

async def _get_user_packs(user_id: int, stype: str) -> list:
    doc = await packsdb.find_one({"user_id": user_id})
    packs = (doc or {}).get("packs", [])
    return [p for p in packs if p.get("type", "static") == stype]


async def _save_pack(user_id: int, pack: dict):
    doc = await packsdb.find_one({"user_id": user_id})
    packs = (doc or {}).get("packs", [])
    for i, p in enumerate(packs):
        if p["short"] == pack["short"]:
            packs[i] = pack
            break
    else:
        packs.append(pack)
    await packsdb.update_one(
        {"user_id": user_id}, {"$set": {"packs": packs}}, upsert=True
    )


def _short_name(user_id: int, idx: int, stype: str, bot_uname: str) -> str:
    import re
    safe = re.sub(r"[^a-zA-Z0-9]", "", bot_uname)
    suffix = {"video": "vid", "animated": "anim"}.get(stype, "")
    return f"v{user_id}{suffix}p{idx}_by_{safe}"[:64]


# ── /kang ───────────────────────────────────────────────────────────────────

@app.on_message(filters.command(["kang", "addsticker"]) & ~BANNED_USERS)
async def cmd_kang(client, message):
    user = message.from_user
    if not user:
        return
    reply = message.reply_to_message
    if not reply or not (reply.sticker or reply.photo or reply.document
                         or reply.video or reply.animation):
        return await message.reply_text(
            "❌ <i>Reply to a sticker, image, or video to kang it.</i>"
        )

    # emoji argument (default from existing sticker or 🤔)
    args = (message.text or "").split(None, 1)
    emoji = ""
    if len(args) > 1:
        from ValerieMusic.plugins.tools.stickers import extract_emojis_from_str
        ems = extract_emojis_from_str(args[1])
        emoji = "".join(ems[:1])
    if not emoji and reply.sticker and reply.sticker.emoji:
        emoji = reply.sticker.emoji
    if not emoji:
        emoji = "🤔"

    status = await message.reply_text("📦 <i>Downloading…</i>")

    try:
        data = await _download_bytes(reply)
        if not data:
            return await status.edit_text("❌ <i>Could not download media.</i>")

        stype = _detect_type(reply, data)
        await status.edit_text(f"⚙️ <i>Preparing {stype} sticker…</i>")
        if stype == "static":
            prepared = _prepare_static(data)
        elif stype == "video":
            prepared = _prepare_video(data)
        else:
            prepared = data

        bot_uname = (await app.get_me()).username
        input_doc = await _upload_document(prepared, stype)

        # Find a pack with space, else roll to a new index.
        packs = await _get_user_packs(user.id, stype)
        target = None
        for p in packs:
            if p.get("count", 0) < MAX_PER_PACK:
                target = p
                break

        await status.edit_text("☁️ <i>Adding to your pack…</i>")
        title = f"{user.first_name}'s {('Video ' if stype=='video' else 'Animated ' if stype=='animated' else '')}Pack"

        if target:
            short = target["short"]
            try:
                await _add_to_set(short, input_doc, emoji)
                target["count"] = target.get("count", 0) + 1
                await _save_pack(user.id, target)
            except StickersetInvalid:
                target = None  # set vanished — recreate below

        if not target:
            idx = len(packs) + 1
            short = _short_name(user.id, idx, stype, bot_uname)
            try:
                await _create_set(user.id, short, title, input_doc, emoji, stype)
            except RPCError as e:
                desc = str(e)
                if "PEER_ID_INVALID" in desc or "USER_ID_INVALID" in desc.upper():
                    return await status.edit_text(
                        "❌ <b>Start the bot first.</b>\n"
                        f"<i>Open</i> @{bot_uname} <i>and press Start, then /kang again.</i>"
                    )
                return await status.edit_text(f"❌ <code>{desc}</code>")
            await _save_pack(user.id, {"short": short, "type": stype, "count": 1, "title": title})

        link = f"https://t.me/addstickers/{short}"
        icon = {"video": "🎬", "animated": "✨"}.get(stype, "🖼")
        await status.edit_text(
            f"✅ <b>Sticker Kanged!</b>\n{SEP}\n"
            f"◆ Pack  → <a href=\"{link}\">{title}</a>\n"
            f"◆ Type  → {icon} <code>{stype}</code>\n"
            f"◆ Emoji → {emoji}\n"
            f"◆ Open  → {link}",
            disable_web_page_preview=True,
        )
    except RPCError as e:
        await status.edit_text(f"❌ <code>{e}</code>")
    except Exception as e:
        await status.edit_text(f"❌ <b>Kang failed:</b> <code>{e}</code>")


# ── /mypacks ─────────────────────────────────────────────────────────────────

@app.on_message(filters.command(["mypacks", "packs"]) & ~BANNED_USERS)
async def cmd_mypacks(client, message):
    user = message.from_user
    if not user:
        return
    doc = await packsdb.find_one({"user_id": user.id})
    packs = (doc or {}).get("packs", [])
    if not packs:
        return await message.reply_text(
            "📦 <i>You have no packs yet.</i> Reply to a sticker with /kang to start one."
        )
    lines = [f"📦 <b>Your Sticker Packs</b>\n{SEP}"]
    for p in packs:
        icon = {"video": "🎬", "animated": "✨"}.get(p.get("type"), "🖼")
        link = f"https://t.me/addstickers/{p['short']}"
        lines.append(
            f'{icon} <a href="{link}">{p.get("title","Pack")}</a> — '
            f'<code>{p.get("count",0)}/{MAX_PER_PACK}</code>'
        )
    await message.reply_text("\n".join(lines), disable_web_page_preview=True)

import logging
import os
import traceback

import numpy as np
import requests
from PIL import Image

logging.basicConfig(level=logging.INFO)

DEFAULT_THUMB = "ValerieMusic/assets/Thumbnail.png"
CACHED_THUMB = "ValerieMusic/assets/Thumbnail_custom.png"
OUT_THUMB = "ValerieMusic/assets/temp_thumb.png"


def _resolve_base():
    """Return the path to the base thumbnail to composite onto.

    If config.THUMBNAIL_URL is set, download it once to a local cache and use
    that (a real file is required so the cover can be drawn into it). On any
    failure, fall back to the bundled Thumbnail.png.
    """
    try:
        import config
        url = getattr(config, "THUMBNAIL_URL", None)
    except Exception:
        url = None

    if url:
        try:
            if not os.path.exists(CACHED_THUMB):
                r = requests.get(url, timeout=15)
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(CACHED_THUMB, "wb") as f:
                        f.write(r.content)
            if os.path.exists(CACHED_THUMB):
                # Validate it actually opens; otherwise drop the bad cache.
                Image.open(CACHED_THUMB).verify()
                return CACHED_THUMB
        except Exception as e:
            logging.error(f"Custom thumbnail download failed, using default: {e}")
            try:
                if os.path.exists(CACHED_THUMB):
                    os.remove(CACHED_THUMB)
            except Exception:
                pass
    return DEFAULT_THUMB


BASE_THUMB = _resolve_base()

# Cached white-box geometry + shape mask (computed once from BASE_THUMB).
# _BOX = (x0, y0, w, h); _SHAPE = boolean mask (h, w) of the rounded box.
_BOX = None
_SHAPE = None


def _detect_box(base: Image.Image):
    """Locate the white cover placeholder and capture its exact (rounded) shape.

    Returns ((x0, y0, w, h), shape_mask) where shape_mask is a bool array the
    size of the box bbox, True wherever the placeholder is white. Using the
    placeholder pixels themselves as the mask means the cover inherits the
    box's rounded corners automatically.
    """
    arr = np.asarray(base.convert("RGB"))
    white = (arr[:, :, 0] > 180) & (arr[:, :, 1] > 180) & (arr[:, :, 2] > 180)

    # Box columns = those with many white pixels. The placeholder is the
    # left-most such block; the logo/text lives on the right, so take the
    # first contiguous run of qualifying columns.
    col_white = white.sum(axis=0)
    cols = np.where(col_white > 200)[0]
    if cols.size == 0:
        raise ValueError("No white placeholder found in base thumbnail")
    x0 = int(cols[0])
    x1 = x0
    for c in cols:
        if c <= x1 + 3:  # allow tiny gaps from rounded edges / anti-aliasing
            x1 = int(c)
        else:
            break

    region = white[:, x0:x1 + 1]
    rows = np.where(region.sum(axis=1) > 200)[0]
    y0, y1 = int(rows[0]), int(rows[-1])

    shape = white[y0:y1 + 1, x0:x1 + 1]
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1), shape


def _ensure_box():
    global _BOX, _SHAPE
    if _BOX is None:
        base = Image.open(BASE_THUMB)
        _BOX, _SHAPE = _detect_box(base)
    return _BOX, _SHAPE


def _square_cover(img: Image.Image, size_w: int, size_h: int) -> Image.Image:
    """Center-crop to a square, then resize to fill the box exactly."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    return img.resize((size_w, size_h), Image.LANCZOS)


async def gen_thumb(videoid: str):
    try:
        (x0, y0, bw, bh), shape = _ensure_box()

        # 1) Download the cover. Try max-res, fall back to hqdefault.
        cover = None
        for name in ("maxresdefault", "hqdefault"):
            url = f"https://i.ytimg.com/vi/{videoid}/{name}.jpg"
            try:
                r = requests.get(url, timeout=10)
            except Exception:
                continue
            if r.status_code == 200 and len(r.content) > 1000:
                tmp = "ValerieMusic/assets/yt.jpg"
                with open(tmp, "wb") as f:
                    f.write(r.content)
                try:
                    cover = Image.open(tmp).convert("RGB")
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                break
        if cover is None:
            return BASE_THUMB

        # 2) Square-crop + resize to fill the placeholder.
        cover = _square_cover(cover, bw, bh)

        # 3) Composite onto the base, clipped to the box's rounded shape.
        base = Image.open(BASE_THUMB).convert("RGB")
        mask = Image.fromarray((shape * 255).astype("uint8"), mode="L")
        base.paste(cover, (x0, y0), mask)

        # 4) Save.
        base.save(OUT_THUMB, "PNG")
        return OUT_THUMB

    except Exception as e:
        logging.error(f"Thumbnail generation error: {e}")
        traceback.print_exc()
        return BASE_THUMB

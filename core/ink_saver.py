"""
Printer InkSaver - Core Image & PDF Ink Saving Engine
Modes:
  - normal: 0% saving, original quality
  - eco: ~25% saving, gamma correction & contrast lightening
  - matrix: ~50% saving, Bayer 8x8 ordered dithering / halftone dot matrix
  - slide_clean: ~60% saving, dark slide background whitening & inverted text
  - line_art: ~75% saving, Canny edge & contour sketch (black on white)
"""

import io
import os
import warnings
from PIL import Image, ImageOps, ImageFilter, ImageChops

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import fitz  # PyMuPDF

if os.environ.get("INKYARD_SKIP_NUMPY", "").strip() == "1":
    np = None
    HAS_NUMPY = False
else:
    try:
        import numpy as np
        HAS_NUMPY = True
    except Exception:
        np = None
        HAS_NUMPY = False

if os.environ.get("INKYARD_SKIP_CV2", "").strip() == "1" or not HAS_NUMPY:
    cv2 = None
    HAS_CV2 = False
else:
    try:
        import cv2
        HAS_CV2 = True
    except Exception:
        cv2 = None
        HAS_CV2 = False

# Precomputed 8x8 Bayer dithering matrix scaled to 0-252 (pure Python list + optional NumPy array)
BAYER_8X8_LIST = [
    [0.0, 128.0,  32.0, 160.0,   8.0, 136.0,  40.0, 168.0],
    [192.0, 64.0, 224.0, 96.0, 200.0,  72.0, 232.0, 104.0],
    [48.0, 176.0, 16.0, 144.0,  56.0, 184.0,  24.0, 152.0],
    [240.0, 112.0, 208.0, 80.0, 248.0, 120.0, 216.0, 88.0],
    [12.0, 140.0, 44.0, 172.0,   4.0, 132.0,  36.0, 164.0],
    [204.0, 76.0, 236.0, 108.0, 196.0, 68.0, 228.0, 100.0],
    [60.0, 188.0, 28.0, 156.0,  52.0, 180.0,  20.0, 148.0],
    [252.0, 124.0, 220.0, 92.0, 244.0, 116.0, 212.0, 84.0],
]

BAYER_8X8 = np.array(BAYER_8X8_LIST, dtype=np.float32) if (HAS_NUMPY and np is not None) else BAYER_8X8_LIST


def _can_use_numpy() -> bool:
    """Return True if numpy is loaded and not disabled via environment."""
    return bool(np is not None and os.environ.get("INKYARD_SKIP_NUMPY", "").strip() != "1")


def _can_use_cv2() -> bool:
    """Return True if both cv2 and numpy are loaded and not disabled via environment."""
    return bool(
        cv2 is not None
        and _can_use_numpy()
        and os.environ.get("INKYARD_SKIP_CV2", "").strip() != "1"
    )


def _to_pil_gray(img) -> Image.Image:
    """Convert a numpy BGR/gray array or PIL.Image into a grayscale ('L') PIL.Image."""
    if isinstance(img, Image.Image):
        return img.convert("L")
    if np is not None and isinstance(img, np.ndarray):
        if img.ndim == 2:
            return Image.fromarray(img)
        if img.shape[2] == 1:
            return Image.fromarray(img[:, :, 0])
        if img.shape[2] == 3:
            return Image.fromarray(img[:, :, ::-1]).convert("L")
        if img.shape[2] == 4:
            return Image.fromarray(img[:, :, [2, 1, 0, 3]]).convert("L")
    raise TypeError(f"Unsupported image type: {type(img)}")


def _to_pil_rgb(img) -> Image.Image:
    """Convert a numpy BGR/gray array or PIL.Image into an 'RGB' PIL.Image."""
    if isinstance(img, Image.Image):
        return img.convert("RGB")
    if np is not None and isinstance(img, np.ndarray):
        if img.ndim == 2:
            return Image.fromarray(img).convert("RGB")
        if img.shape[2] == 1:
            return Image.fromarray(img[:, :, 0]).convert("RGB")
        if img.shape[2] == 3:
            return Image.fromarray(img[:, :, ::-1])
        if img.shape[2] == 4:
            return Image.fromarray(img[:, :, [2, 1, 0, 3]]).convert("RGB")
    raise TypeError(f"Unsupported image type: {type(img)}")


def _from_pil(pil_img: Image.Image, like_img, force_3d: bool = True):
    """Convert a PIL.Image back to the caller's expected representation (numpy BGR array or PIL.Image)."""
    if isinstance(like_img, Image.Image) or not _can_use_numpy():
        return pil_img.convert("RGB") if force_3d else pil_img
    if not force_3d and isinstance(like_img, np.ndarray) and like_img.ndim == 2:
        return np.array(pil_img.convert("L"), dtype=np.uint8)
    rgb_arr = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    return rgb_arr[:, :, ::-1].copy()


def calculate_ink_density(img_bgr) -> float:
    """
    Calculate ink density (0.0 to 1.0) where 0.0 is pure white and 1.0 is pure black.
    """
    if _can_use_cv2() and isinstance(img_bgr, np.ndarray):
        if len(img_bgr.shape) == 3:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_bgr
        # Invert so 0=white (no ink) and 255=black (100% ink)
        ink_values = (255.0 - gray.astype(np.float32)) / 255.0
        return float(np.mean(ink_values))

    gray_pil = _to_pil_gray(img_bgr)
    hist = gray_pil.histogram()
    total = sum(hist)
    if total == 0:
        return 0.0
    mean_gray = sum(i * c for i, c in enumerate(hist)) / float(total)
    return float((255.0 - mean_gray) / 255.0)


def apply_eco_mode(img_bgr, target_saving: float = 0.25, gamma: float = 1.55):
    """
    Eco Mode (Realistic Monochrome Laser Printout):
    - Transforms color into authentic black-and-white laser printer output (B == G == R).
    - Preserves deep, crisp, razor-sharp text and glyphs (pure black stays true dark 0,
      preventing text, bold headings, and Chinese characters from being washed out).
    - Applies gamma curve lightening to large fills, midtone graphics, charts, and photos.
    - Whitens faint off-white background and scan noise (> 215 becomes pure 255).
    - Achieves authentic ~22-26% toner reduction with maximum legibility.
    """
    if _can_use_cv2() and isinstance(img_bgr, np.ndarray):
        if len(img_bgr.shape) == 3:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_bgr.copy()

        # 1. Base eco-tone mapping (gamma curve for midtones & fills)
        floor = 255.0 * target_saving
        inv_gamma = 1.0 / gamma
        table = np.array([
            np.clip(floor + (255.0 - floor) * ((i / 255.0) ** inv_gamma), 0, 255)
            for i in range(256)
        ]).astype(np.uint8)
        enhanced = cv2.LUT(gray, table)

        # 2. Text and fine stroke preservation:
        dark_mask = (gray < 115).astype(np.uint8)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dark_mask)
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            widths = stats[1:, cv2.CC_STAT_WIDTH]
            heights = stats[1:, cv2.CC_STAT_HEIGHT]
            is_text = (areas <= 3500) | ((areas <= 6000) & ((widths <= 50) | (heights <= 50)))
            label_is_text = np.zeros(num_labels, dtype=bool)
            label_is_text[1:] = is_text
            text_mask = label_is_text[labels]
        else:
            text_mask = np.zeros_like(gray, dtype=bool)

        # Stroke width preservation: prevents bold headings & Chinese characters touching rules from washing out
        dist = cv2.distanceTransform(dark_mask, cv2.DIST_L2, 3)
        stroke_mask = (dark_mask > 0) & (dist <= 4.0)

        # Edges of dark regions (keeps crisp 1-2px border on large filled shapes)
        edges = cv2.Canny(gray, 40, 140)
        preserve_mask = text_mask | stroke_mask | ((edges > 0) & (gray < 140))
        enhanced[preserve_mask] = np.minimum(enhanced[preserve_mask], gray[preserve_mask])

        # 3. Suppress faint scan/paper noise (> 215 becomes pure white 255)
        enhanced[gray > 215] = 255

        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    # Pure-Pillow fallback (when cv2 is unavailable or disabled on older CPUs)
    gray_pil = _to_pil_gray(img_bgr)
    floor = 255.0 * target_saving
    inv_gamma = 1.0 / gamma
    lut = []
    for i in range(256):
        if i > 215:
            lut.append(255)
        else:
            val = int(round(min(255.0, max(0.0, floor + (255.0 - floor) * ((i / 255.0) ** inv_gamma)))))
            lut.append(val)
    enhanced_pil = gray_pil.point(lut)

    # Preserve fine dark text, bold headings (where 51x51 neighborhood has white space > 135),
    # and crisp 1-2px borders on large solid blocks (MaxFilter(3) > 180).
    local_max = gray_pil.filter(ImageFilter.MaxFilter(3))
    local_avg = gray_pil.filter(ImageFilter.BoxBlur(25))
    dark_mask = gray_pil.point(lambda p: 255 if p < 115 else 0)
    edge_or_text_mask = ImageChops.lighter(
        local_max.point(lambda p: 255 if p > 180 else 0),
        local_avg.point(lambda p: 255 if p > 110 else 0)
    )
    preserve_mask = ImageChops.darker(dark_mask, edge_or_text_mask)
    darker_gray = ImageChops.darker(enhanced_pil, gray_pil)
    out_gray = Image.composite(darker_gray, enhanced_pil, preserve_mask)
    return _from_pil(out_gray.convert("RGB"), img_bgr, force_3d=True)


def apply_matrix_mode(img_bgr, target_saving: float = 0.50):
    """
    Matrix / Dot-Matrix Mode:
    - Simulates retro dot matrix / newspaper printing using Bayer 8x8 Ordered Dithering.
    - Maps solid black (0) to the 50% dithering threshold (128) of the Bayer matrix,
      creating a crisp 50% micro-dot pattern inside dark text and shapes.
    - Preserves high-frequency stroke edges so text never loses boundary sharpness.
    - Achieves true measured ~48-52% toner reduction.
    """
    if _can_use_cv2() and isinstance(img_bgr, np.ndarray):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Text edge preservation: detect fine stroke edges to keep letter outlines sharp
        edges = cv2.Canny(gray, 50, 150)

        # Map luminance: pure black (0) maps to target threshold (127.5 for 50% dot matrix)
        base_thresh = 255.0 * target_saving
        gray_mapped = base_thresh + (gray.astype(np.float32) / 255.0) * (255.0 - base_thresh)

        tile_y = (h + 7) // 8
        tile_x = (w + 7) // 8
        bayer_arr = BAYER_8X8 if isinstance(BAYER_8X8, np.ndarray) else np.array(BAYER_8X8_LIST, dtype=np.float32)
        threshold_map = np.tile(bayer_arr, (tile_y, tile_x))[:h, :w]

        dithered = np.where(gray_mapped >= threshold_map, 255, 0).astype(np.uint8)

        # Reinforce the thinnest stroke boundary outlines so fine text remains razor-sharp
        dilated_edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
        dark_edges = (dilated_edges > 0) & (gray < 60)
        dithered[dark_edges] = np.where((threshold_map[dark_edges] > 180), 0, dithered[dark_edges])

        return cv2.cvtColor(dithered, cv2.COLOR_GRAY2BGR)

    # Pure-Pillow / NumPy fallback without cv2
    gray_pil = _to_pil_gray(img_bgr)
    w, h = gray_pil.size
    base_thresh = 255.0 * target_saving

    if _can_use_numpy():
        gray = np.array(gray_pil, dtype=np.uint8)
        gray_mapped = base_thresh + (gray.astype(np.float32) / 255.0) * (255.0 - base_thresh)
        bayer_arr = BAYER_8X8 if isinstance(BAYER_8X8, np.ndarray) else np.array(BAYER_8X8_LIST, dtype=np.float32)
        tile_y = (h + 7) // 8
        tile_x = (w + 7) // 8
        threshold_map = np.tile(bayer_arr, (tile_y, tile_x))[:h, :w]
        dithered = np.where(gray_mapped >= threshold_map, 255, 0).astype(np.uint8)
        dithered_pil = Image.fromarray(dithered).convert("RGB")
        return _from_pil(dithered_pil, img_bgr, force_3d=True)

    # Pure-Pillow fallback when both cv2 and numpy are disabled (C-accelerated via ImageChops)
    mapped_lut = [int(round(base_thresh + (i / 255.0) * (255.0 - base_thresh))) for i in range(256)]
    mapped_pil = gray_pil.point(mapped_lut)
    tile_x = (w + 7) // 8
    tile_y = (h + 7) // 8
    row_patterns = [(bytes(int(v) for v in row) * tile_x)[:w] for row in BAYER_8X8_LIST]
    thresh_bytes = (b"".join(row_patterns) * tile_y)[: w * h]
    thresh_pil = Image.frombytes("L", (w, h), thresh_bytes)
    # max(0, thresh - mapped) == 0 iff mapped >= thresh
    diff_pil = ImageChops.subtract(thresh_pil, mapped_pil)
    dithered_pil = diff_pil.point([255] + [0] * 255).convert("RGB")
    return _from_pil(dithered_pil, img_bgr, force_3d=True)


def is_dark_background(gray_or_bgr) -> bool:
    """
    Detects whether an image/page has a predominantly dark background (e.g. chalkboard,
    dark lecture slide, night-mode PDF) as opposed to a white/light paper document.
    """
    if _can_use_cv2() and isinstance(gray_or_bgr, np.ndarray):
        if len(gray_or_bgr.shape) == 3:
            gray = cv2.cvtColor(gray_or_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = gray_or_bgr

        mean_val = float(np.mean(gray))
        median_val = float(np.median(gray))

        if mean_val >= 140 or median_val >= 140:
            return False

        dark_ratio = float(np.mean(gray < 100))
        return bool((dark_ratio > 0.45) and (mean_val < 115) and (median_val < 130))

    gray_pil = _to_pil_gray(gray_or_bgr)
    hist = gray_pil.histogram()
    total = sum(hist)
    if total == 0:
        return False
    mean_val = sum(i * c for i, c in enumerate(hist)) / float(total)
    half = total / 2.0
    cum = 0
    median_val = 255.0
    for i, c in enumerate(hist):
        cum += c
        if cum >= half:
            median_val = float(i)
            break

    if mean_val >= 140 or median_val >= 140:
        return False

    dark_ratio = sum(hist[:100]) / float(total)
    return bool((dark_ratio > 0.45) and (mean_val < 115) and (median_val < 130))


def apply_slide_clean_mode(img_bgr):
    """
    Slide Clean / Dark Background Whitening Mode:
    - Specifically designed for lecture PPT slides with black or dark blue backgrounds.
    - Turns dark backgrounds pure white (RGB 255, 255, 255).
    - Inverts light text to dark text so white-on-black becomes black-on-white.
    - For already-light slides, whitens background noise and applies eco-lightening.
    - Saves 60-90% ink on presentation slides.
    """
    if _can_use_cv2() and isinstance(img_bgr, np.ndarray):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        is_dark = is_dark_background(gray)

        result = img_bgr.copy()
        if is_dark:
            dark_bg_mask = gray < 85
            light_content_mask = gray > 165
            mid_mask = (~dark_bg_mask) & (~light_content_mask)

            result[dark_bg_mask] = [255, 255, 255]
            result[light_content_mask] = [30, 30, 30]

            if np.any(mid_mask):
                inv_mid = 255 - result[mid_mask]
                result[mid_mask] = inv_mid
        else:
            white_thresh = gray > 215
            result[white_thresh] = [255, 255, 255]
            result = apply_eco_mode(result, target_saving=0.20)

        return result

    # Pure-Pillow fallback
    gray_pil = _to_pil_gray(img_bgr)
    rgb_pil = _to_pil_rgb(img_bgr)
    is_dark = is_dark_background(gray_pil)

    if is_dark:
        inv_rgb = ImageOps.invert(rgb_pil)
        white_img = Image.new("RGB", rgb_pil.size, (255, 255, 255))
        charcoal_img = Image.new("RGB", rgb_pil.size, (30, 30, 30))
        dark_bg_mask = gray_pil.point(lambda p: 255 if p < 85 else 0)
        light_content_mask = gray_pil.point(lambda p: 255 if p > 165 else 0)
        res_pil = Image.composite(charcoal_img, inv_rgb, light_content_mask)
        res_pil = Image.composite(white_img, res_pil, dark_bg_mask)
        return _from_pil(res_pil, img_bgr, force_3d=True)
    else:
        white_img = Image.new("RGB", rgb_pil.size, (255, 255, 255))
        white_mask = gray_pil.point(lambda p: 255 if p > 215 else 0)
        res_pil = Image.composite(white_img, rgb_pil, white_mask)
        return apply_eco_mode(_from_pil(res_pil, img_bgr, force_3d=True), target_saving=0.20)


def apply_line_art_mode(img_bgr):
    """
    Line Art / Sketch Mode:
    - Extracts clean contours and stroke edges on a pure white background.
    - Replaces thick black fills and photo areas with outlines, sparing ~75%+ ink.
    """
    if _can_use_cv2() and isinstance(img_bgr, np.ndarray):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        kernel = np.ones((2, 2), np.uint8)
        gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
        outline = np.where((edges > 0) | ((gradient > 50) & (gray < 180)), 0, 255).astype(np.uint8)
        return cv2.cvtColor(outline, cv2.COLOR_GRAY2BGR)

    gray_pil = _to_pil_gray(img_bgr)
    max_p = gray_pil.filter(ImageFilter.MaxFilter(3))
    min_p = gray_pil.filter(ImageFilter.MinFilter(3))
    grad = ImageChops.subtract(max_p, min_p)
    outline_pil = grad.point(lambda p: 0 if p > 35 else 255).convert("RGB")
    return _from_pil(outline_pil, img_bgr, force_3d=True)


def apply_smart_inversion(img_bgr):
    """
    Intelligent Color Inversion / Slide Whitening:
    - If the page has a dark background (lecture slides, chalkboard PDFs, dark-mode documents):
      inverts dark background to pure white paper (255) and light text to dark text (30),
      drastically slashing toner waste by 60-90%.
    - If the page already has a light / white paper background:
      GUARDS against disastrous toner waste: NEVER inverts white paper into solid black toner.
      Cleans faint paper/scan background noise to pure white (255).
      Inverts large solid dark fills/banners to white while preserving white text inside
      the banner by mapping it to crisp dark charcoal (30).
    """
    if _can_use_cv2() and isinstance(img_bgr, np.ndarray):
        is_3d = len(img_bgr.shape) == 3
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if is_3d else img_bgr.copy()
        is_dark = is_dark_background(gray)

        if is_dark:
            dark_bg_mask = gray < 85
            light_content_mask = gray > 165
            mid_mask = (~dark_bg_mask) & (~light_content_mask)
            if is_3d:
                result = img_bgr.copy()
                result[dark_bg_mask] = [255, 255, 255]
                result[light_content_mask] = [30, 30, 30]
                if np.any(mid_mask):
                    result[mid_mask] = 255 - result[mid_mask]
                return result
            else:
                result = gray.copy()
                result[dark_bg_mask] = 255
                result[light_content_mask] = 30
                if np.any(mid_mask):
                    result[mid_mask] = 255 - result[mid_mask]
                return result

        # Light background (normal document / white paper):
        result = img_bgr.copy()
        white_thresh = gray > 215
        if is_3d:
            result[white_thresh] = [255, 255, 255]
        else:
            result[white_thresh] = 255

        # Invert large solid dark fills/blocks (not fine text strokes)
        dark_mask = (gray < 115).astype(np.uint8)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dark_mask)
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            widths = stats[1:, cv2.CC_STAT_WIDTH]
            heights = stats[1:, cv2.CC_STAT_HEIGHT]
            is_large_dark_block = (areas > 3500) & (widths > 40) & (heights > 35)
            for i in range(1, num_labels):
                if is_large_dark_block[i - 1]:
                    mask_i = (labels == i)
                    x = stats[i, cv2.CC_STAT_LEFT]
                    y = stats[i, cv2.CC_STAT_TOP]
                    w = stats[i, cv2.CC_STAT_WIDTH]
                    h = stats[i, cv2.CC_STAT_HEIGHT]
                    if is_3d:
                        result[mask_i] = [255, 255, 255]
                    else:
                        result[mask_i] = 255

                    sub_mask = mask_i[y:y+h, x:x+w].astype(np.uint8)
                    sub_gray = gray[y:y+h, x:x+w]
                    contours, _ = cv2.findContours(sub_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if contours:
                        filled = np.zeros_like(sub_mask)
                        cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
                        text_holes = (filled == 1) & (sub_mask == 0) & (sub_gray > 160)
                        if np.any(text_holes):
                            sub_res = result[y:y+h, x:x+w]
                            if is_3d:
                                sub_res[text_holes] = [30, 30, 30]
                            else:
                                sub_res[text_holes] = 30

        return result

    # Pure-Pillow fallback
    is_2d_np = bool(_can_use_numpy() and isinstance(img_bgr, np.ndarray) and img_bgr.ndim == 2)
    gray_pil = _to_pil_gray(img_bgr)
    rgb_pil = _to_pil_rgb(img_bgr)
    is_dark = is_dark_background(gray_pil)

    if is_dark:
        inv_rgb = ImageOps.invert(rgb_pil)
        white_img = Image.new("RGB", rgb_pil.size, (255, 255, 255))
        charcoal_img = Image.new("RGB", rgb_pil.size, (30, 30, 30))
        dark_bg_mask = gray_pil.point(lambda p: 255 if p < 85 else 0)
        light_content_mask = gray_pil.point(lambda p: 255 if p > 165 else 0)
        res_pil = Image.composite(charcoal_img, inv_rgb, light_content_mask)
        res_pil = Image.composite(white_img, res_pil, dark_bg_mask)
        return _from_pil(res_pil, img_bgr, force_3d=not is_2d_np)

    # Light background in pure Pillow: clean off-white noise, whiten deep solid block interiors,
    # and map white text holes inside dark banners to crisp dark charcoal (30, 30, 30).
    white_img = Image.new("RGB", rgb_pil.size, (255, 255, 255))
    charcoal_img = Image.new("RGB", rgb_pil.size, (30, 30, 30))
    white_mask = gray_pil.point(lambda p: 255 if p > 215 else 0)
    res_pil = Image.composite(white_img, rgb_pil, white_mask)

    local_max = gray_pil.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MaxFilter(5))
    deep_block_mask = local_max.point(lambda p: 255 if p < 100 else 0)
    res_pil = Image.composite(white_img, res_pil, deep_block_mask)

    blurred = gray_pil.filter(ImageFilter.BoxBlur(18))
    in_dark_banner_mask = blurred.point(lambda p: 255 if p < 130 else 0)
    banner_bg_mask = ImageChops.darker(gray_pil.point(lambda p: 255 if p < 115 else 0), in_dark_banner_mask)
    res_pil = Image.composite(white_img, res_pil, banner_bg_mask)
    banner_white_text_mask = ImageChops.darker(gray_pil.point(lambda p: 255 if p > 160 else 0), in_dark_banner_mask)
    res_pil = Image.composite(charcoal_img, res_pil, banner_white_text_mask)
    return _from_pil(res_pil, img_bgr, force_3d=not is_2d_np)


def process_image(img_bgr, mode: str = "eco", invert_color: bool = False):
    """
    Dispatch image processing according to selected mode, with optional smart color inversion.
    """
    if invert_color:
        img_bgr = apply_smart_inversion(img_bgr)

    mode = (mode or "eco").lower().strip()
    if mode == "eco":
        return apply_eco_mode(img_bgr)
    elif mode == "matrix":
        return apply_matrix_mode(img_bgr)
    elif mode == "slide_clean":
        return apply_slide_clean_mode(img_bgr)
    elif mode == "line_art":
        return apply_line_art_mode(img_bgr)
    else:  # "normal" or unknown
        return img_bgr


def parse_page_range(range_str: str, max_pages: int) -> list:
    """
    Parse page ranges like '1-3, 5, 7-9' (1-indexed) into 0-indexed integer list.
    """
    if not range_str or range_str.strip().lower() in ("all", "*", ""):
        return list(range(max_pages))

    pages = set()
    parts = range_str.replace(" ", "").split(",")
    for part in parts:
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start = max(1, int(start_s))
                end = min(max_pages, int(end_s))
                for p in range(start, end + 1):
                    pages.add(p - 1)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= max_pages:
                    pages.add(p - 1)
            except ValueError:
                continue

    result = sorted(list(pages))
    return result if result else list(range(max_pages))


def _pixmap_to_img(pix):
    """Convert a PyMuPDF Pixmap into a numpy BGR array (or PIL Image when numpy/cv2 unavailable)."""
    if _can_use_cv2():
        img_rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n == 4:
            return cv2.cvtColor(img_rgb, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        else:
            return cv2.cvtColor(img_rgb, cv2.COLOR_GRAY2BGR)

    pil_mode = "RGBA" if pix.n == 4 else ("RGB" if pix.n == 3 else "L")
    pil_img = Image.frombytes(pil_mode, (pix.width, pix.height), pix.samples).convert("RGB")
    if _can_use_numpy():
        return np.array(pil_img, dtype=np.uint8)[:, :, ::-1].copy()
    return pil_img


def _encode_image_bytes(img, fmt: str = ".jpg", quality: int = 85) -> bytes:
    """Encode a numpy BGR array or PIL Image to JPEG or PNG bytes."""
    if _can_use_cv2() and isinstance(img, np.ndarray):
        if fmt.lower() == ".png":
            _, enc = cv2.imencode(".png", img)
        else:
            _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return enc.tobytes()

    pil_img = _to_pil_rgb(img)
    buf = io.BytesIO()
    if fmt.lower() == ".png":
        pil_img.save(buf, format="PNG")
    else:
        pil_img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def generate_page_preview(
    pdf_path: str,
    page_num: int = 0,
    mode: str = "eco",
    max_dim: int = 850,
    invert_color: bool = False
) -> dict:
    """
    Quickly generates an original and processed preview image for a specific page.
    Supports inverse color (negative mode).
    """
    import base64

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    page_num = max(0, min(page_num, total_pages - 1))
    page = doc[page_num]

    # Calculate scale so max dimension <= max_dim (fast render)
    rect = page.rect
    w, h = rect.width, rect.height
    scale = min(max_dim / max(w, h, 1), 2.0)
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bgr = _pixmap_to_img(pix)
    doc.close()

    orig_density = calculate_ink_density(img_bgr)
    orig_bgr = img_bgr.copy()

    # Detect if original source page has a dark background
    is_dark_bg = is_dark_background(img_bgr)

    # Process with selected mode and color inversion
    proc_bgr = process_image(img_bgr, mode=mode, invert_color=invert_color)
    proc_density = calculate_ink_density(proc_bgr)

    if orig_density > 0.005:
        ink_saved_pct = max(0.0, (1.0 - (proc_density / orig_density)) * 100.0)
    else:
        ink_saved_pct = 0.0

    # Encode original (un-inverted true source) and processed to JPEG
    orig_bytes = _encode_image_bytes(orig_bgr, fmt=".jpg", quality=85)
    proc_bytes = _encode_image_bytes(proc_bgr, fmt=".jpg", quality=85)

    return {
        "page": page_num + 1,
        "total_pages": total_pages,
        "mode": mode,
        "invert_color": invert_color,
        "is_dark_bg": is_dark_bg,
        "orig_b64": "data:image/jpeg;base64," + base64.b64encode(orig_bytes).decode("utf-8"),
        "proc_b64": "data:image/jpeg;base64," + base64.b64encode(proc_bytes).decode("utf-8"),
        "ink_saved_pct": round(ink_saved_pct, 1),
        "orig_ink_density": round(orig_density * 100, 2),
        "proc_ink_density": round(proc_density * 100, 2)
    }


def apply_nup_layout(src_doc: fitz.Document, nup: int = 1) -> fitz.Document:
    """
    Rearranges PDF pages into N-up sheets (2-up or 4-up per physical sheet).
    Auto-detects page orientation (portrait vs landscape) to maximize slide readability.
    """
    if nup <= 1 or len(src_doc) == 0:
        return src_doc

    doc_nup = fitz.open()
    total = len(src_doc)
    is_landscape = src_doc[0].rect.width > src_doc[0].rect.height

    if nup == 2:
        if is_landscape:
            sheet_w, sheet_h = 595.0, 842.0
            margin = 16.0
            gap = 12.0
            half_h = (sheet_h - (2 * margin) - gap) / 2.0
            rect_top = fitz.Rect(margin, margin, sheet_w - margin, margin + half_h)
            rect_bottom = fitz.Rect(margin, margin + half_h + gap, sheet_w - margin, sheet_h - margin)

            for i in range(0, total, 2):
                sheet = doc_nup.new_page(width=sheet_w, height=sheet_h)
                sheet.show_pdf_page(rect_top, src_doc, i)
                if i + 1 < total:
                    sheet.show_pdf_page(rect_bottom, src_doc, i + 1)
        else:
            sheet_w, sheet_h = 842.0, 595.0
            margin = 16.0
            gap = 12.0
            half_w = (sheet_w - (2 * margin) - gap) / 2.0
            rect_left = fitz.Rect(margin, margin, margin + half_w, sheet_h - margin)
            rect_right = fitz.Rect(margin + half_w + gap, margin, sheet_w - margin, sheet_h - margin)

            for i in range(0, total, 2):
                sheet = doc_nup.new_page(width=sheet_w, height=sheet_h)
                sheet.show_pdf_page(rect_left, src_doc, i)
                if i + 1 < total:
                    sheet.show_pdf_page(rect_right, src_doc, i + 1)

    elif nup == 4:
        if is_landscape:
            sheet_w, sheet_h = 842.0, 595.0
            margin = 16.0
            gap_x = 10.0
            gap_y = 10.0
            half_w = (sheet_w - (2 * margin) - gap_x) / 2.0
            half_h = (sheet_h - (2 * margin) - gap_y) / 2.0
            rects = [
                fitz.Rect(margin, margin, margin + half_w, margin + half_h),
                fitz.Rect(margin + half_w + gap_x, margin, sheet_w - margin, margin + half_h),
                fitz.Rect(margin, margin + half_h + gap_y, margin + half_w, sheet_h - margin),
                fitz.Rect(margin + half_w + gap_x, margin + half_h + gap_y, sheet_w - margin, sheet_h - margin)
            ]
        else:
            sheet_w, sheet_h = 595.0, 842.0
            margin = 16.0
            gap_x = 10.0
            gap_y = 10.0
            half_w = (sheet_w - (2 * margin) - gap_x) / 2.0
            half_h = (sheet_h - (2 * margin) - gap_y) / 2.0
            rects = [
                fitz.Rect(margin, margin, margin + half_w, margin + half_h),
                fitz.Rect(margin + half_w + gap_x, margin, sheet_w - margin, margin + half_h),
                fitz.Rect(margin, margin + half_h + gap_y, margin + half_w, sheet_h - margin),
                fitz.Rect(margin + half_w + gap_x, margin + half_h + gap_y, sheet_w - margin, sheet_h - margin)
            ]

        for i in range(0, total, 4):
            sheet = doc_nup.new_page(width=sheet_w, height=sheet_h)
            for slot, r in enumerate(rects):
                if i + slot < total:
                    sheet.show_pdf_page(r, src_doc, i + slot)
    else:
        return src_doc

    return doc_nup


def process_pdf_document(
    input_pdf_path: str,
    output_pdf_path: str,
    mode: str = "eco",
    page_range_str: str = "all",
    dpi: int = 180,
    invert_color: bool = False,
    nup: int = 1
) -> dict:
    """
    Renders selected PDF pages, applies the ink-saving pipeline (with optional color inversion),
    applies optional N-up layout (1-up, 2-up, 4-up), and builds an optimized output PDF.
    """
    doc_in = fitz.open(input_pdf_path)
    total_pages = len(doc_in)
    target_pages = parse_page_range(page_range_str, total_pages)

    # If mode is normal, no color inversion, nup==1, and all pages selected: fast copy
    if (mode == "normal" or not mode) and not invert_color and nup <= 1 and len(target_pages) == total_pages:
        doc_in.save(output_pdf_path, garbage=3, deflate=True)
        doc_in.close()
        return {
            "input_pages": total_pages,
            "printed_pages": total_pages,
            "printed_sheets": total_pages,
            "mode": "normal",
            "invert_color": False,
            "nup": 1,
            "avg_ink_saved_pct": 0.0,
            "est_ink_saved_ml": 0.0,
            "output_file": output_pdf_path
        }

    doc_out = fitz.open()
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)

    total_savings = []

    for page_idx in target_pages:
        page = doc_in[page_idx]
        rect = page.rect

        if (mode == "normal" or not mode) and not invert_color:
            # Copy original vector page directly
            doc_out.insert_pdf(doc_in, from_page=page_idx, to_page=page_idx)
            total_savings.append(0.0)
            continue

        # Render page
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bgr = _pixmap_to_img(pix)

        orig_density = calculate_ink_density(img_bgr)

        proc_bgr = process_image(img_bgr, mode=mode, invert_color=invert_color)
        proc_density = calculate_ink_density(proc_bgr)

        if orig_density > 0.005:
            saving = max(0.0, (1.0 - (proc_density / orig_density)) * 100.0)
        else:
            saving = 0.0

        total_savings.append(saving)

        # Compress processed image to JPEG/PNG bytes
        if mode in ("matrix", "line_art"):
            img_bytes = _encode_image_bytes(proc_bgr, fmt=".png")
        else:
            img_bytes = _encode_image_bytes(proc_bgr, fmt=".jpg", quality=88)

        # Create output page matching original dimensions
        new_page = doc_out.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=img_bytes)

    doc_in.close()

    # Apply N-up layout if requested (2-up or 4-up)
    if nup in (2, 4):
        doc_final = apply_nup_layout(doc_out, nup=nup)
        doc_final.save(output_pdf_path, garbage=4, deflate=True)
        printed_sheets = len(doc_final)
        doc_final.close()
        doc_out.close()
    else:
        doc_out.save(output_pdf_path, garbage=4, deflate=True)
        printed_sheets = len(doc_out)
        doc_out.close()

    avg_saving = float(sum(total_savings) / len(total_savings)) if total_savings else 0.0
    est_ink_ml = len(target_pages) * 0.05 * (avg_saving / 100.0)

    return {
        "input_pages": total_pages,
        "printed_pages": len(target_pages),
        "printed_sheets": printed_sheets,
        "mode": mode,
        "invert_color": invert_color,
        "nup": nup,
        "avg_ink_saved_pct": round(avg_saving, 1),
        "est_ink_saved_ml": round(est_ink_ml, 3),
        "output_file": output_pdf_path
    }

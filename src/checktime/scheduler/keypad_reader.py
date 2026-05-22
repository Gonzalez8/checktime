"""
Read the CheckJC verification keypad to build a letter -> digit mapping.

CheckJC's /verification page renders 10 keypad buttons, each carrying a
``data-value`` attribute with a random per-session uppercase letter (A-Z).
Each button also embeds a small undistorted PNG that displays the digit
(0-9) the letter represents on this session.

The letter set and the letter->digit mapping are STABLE for the entire
session — only the buttons' physical positions reshuffle after each
click. We therefore only need to read each button once at the start and
keep the mapping in memory.

This module owns the OCR for those undistorted PNGs (Tesseract via
pytesseract). Distinguishing 10 clean digits is trivial OCR; we whitelist
``0123456789`` and use psm=10 (single character).
"""

from __future__ import annotations

import io
import logging
from typing import Dict, Iterable

logger = logging.getLogger(__name__)

# Lazy imports: keep import-time light and let the rest of the code load
# even if Tesseract is missing on a dev box. Production has it in the image.
_TESSERACT_AVAILABLE = None


def _ensure_tesseract():
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        _TESSERACT_AVAILABLE = True
    except Exception as exc:
        logger.error("Tesseract/Pillow not available: %s", exc)
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def read_digit_from_png(png_bytes: bytes) -> str | None:
    """
    Return the digit ('0'-'9') visible in a single keypad button PNG, or
    None if OCR failed.

    The keypad button images are tiny (~50x30 px), one digit per image,
    with a thin decorative underline in a random color. Tesseract with
    ``--psm 10`` and a digit whitelist handles this reliably.
    """
    if not _ensure_tesseract():
        return None
    import pytesseract
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(png_bytes))
        # Upscale 4x; gives Tesseract more pixels to work with on tiny images
        img = img.convert("L").resize((img.width * 4, img.height * 4))
        text = pytesseract.image_to_string(
            img,
            config="--psm 10 -c tessedit_char_whitelist=0123456789",
        ).strip()
    except Exception as exc:
        logger.warning("OCR failed on a keypad button: %s", exc)
        return None

    # Tesseract sometimes returns extra whitespace/newlines; keep digits only
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 1:
        return digits
    if len(digits) > 1:
        # Conservative: prefer the first digit if Tesseract sees noise
        logger.debug("OCR returned multi-digit %r, taking first", digits)
        return digits[0]
    return None


def build_letter_to_digit_map(buttons: Iterable[tuple[str, bytes]]) -> Dict[str, str]:
    """
    Build a mapping ``{letter: digit}`` from the keypad buttons.

    ``buttons`` is an iterable of ``(letter, png_bytes)`` pairs — one per
    keypad button (typically 10).

    Returns the partial mapping for whatever letters we could resolve. The
    caller decides what to do with missing entries (usually: bail out and
    raise CheckJCFormError so the human notices CheckJC may have changed).
    """
    mapping: Dict[str, str] = {}
    for letter, png_bytes in buttons:
        digit = read_digit_from_png(png_bytes)
        if digit is not None:
            mapping[letter] = digit
        else:
            logger.warning("Could not OCR keypad button for letter %r", letter)
    logger.info("Resolved keypad mapping: %s", mapping)
    return mapping

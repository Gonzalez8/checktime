"""
Captcha solvers for CheckJC's /portal/employee/verification page.

The scheduler captures the distorted 6-digit captcha image during login and
hands it to a CaptchaSolver. Solvers receive the raw image bytes and must
return the 6-digit solution as a string (or None if they could not solve it
within their own timeout).

Two implementations live here:

- ``TelegramHumanSolver`` is the production solver today: it persists a
  PendingCaptcha row, ships the image to the user's Telegram chat, and polls
  the DB until the bot listener writes the user's reply back.

- ``LLMVisionSolver`` is a placeholder for the future: same contract, but
  forwards the image to an LLM with vision and parses its response. The
  rest of the codebase only deals with the ``CaptchaSolver`` abstract base,
  so swapping in the LLM-backed one in v1.9+ is a one-line change in
  ``service.py``.
"""

from __future__ import annotations

import io
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple

from checktime.shared.db import db
from checktime.shared.models.captcha import (
    PendingCaptcha,
    STATE_ANSWERED,
    STATE_CONSUMED,
    STATE_EXPIRED,
    STATE_FAILED,
    STATE_WAITING,
)
from checktime.shared.models.user import User
from checktime.utils.telegram import TelegramClient

logger = logging.getLogger(__name__)


# Each keypad entry passed to the solver: (data-value letter, PNG bytes of
# the small undistorted digit image inside the button).
KeypadEntry = Tuple[str, bytes]


def compose_captcha_image(captcha_bytes: bytes, keypad: List[KeypadEntry]) -> bytes:
    """Stack the captcha on top, then a labeled strip of the 10 keypad PNGs.

    Returns a PNG. Used by both TelegramHumanSolver (to ship to the user)
    and LLMVisionSolver (to ship to Gemini).
    """
    from PIL import Image, ImageDraw, ImageFont

    captcha = Image.open(io.BytesIO(captcha_bytes)).convert("RGB")
    button_imgs = [Image.open(io.BytesIO(png)).convert("RGBA") for _, png in keypad]

    target_w = 640
    scale = target_w / captcha.width
    captcha_w = target_w
    captcha_h = int(captcha.height * scale)
    captcha = captcha.resize((captcha_w, captcha_h))

    btn_h = 60
    btn_scale = btn_h / button_imgs[0].height
    btn_w = int(button_imgs[0].width * btn_scale)
    gap = 14
    strip_w = btn_w * 10 + gap * 9 + 20
    label_h = 26
    strip_h = label_h + btn_h + 10

    total_w = max(captcha_w, strip_w) + 20
    total_h = captcha_h + 30 + strip_h + 20
    canvas = Image.new("RGB", (total_w, total_h), (245, 245, 245))

    cx = (total_w - captcha_w) // 2
    canvas.paste(captcha, (cx, 10))

    strip_x0 = (total_w - strip_w) // 2 + 10
    strip_y0 = captcha_h + 30
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18
        )
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for i, bimg in enumerate(button_imgs):
        x = strip_x0 + i * (btn_w + gap)
        draw.text((x + btn_w // 2 - 6, strip_y0), f"{i+1}", fill=(40, 40, 40), font=font)
        bw = bimg.resize((btn_w, btn_h))
        bg = Image.new("RGB", (btn_w, btn_h), (255, 255, 255))
        bg.paste(bw, (0, 0), mask=bw.split()[3] if bw.mode == "RGBA" else None)
        canvas.paste(bg, (x, strip_y0 + label_h))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def translate_16_digits_to_letters(raw: str, keypad: List[KeypadEntry]) -> Optional[List[str]]:
    """Turn "<10 keypad digits><6 captcha digits>" into 6 letters to click.

    Returns None on malformed input. Shared by both solvers — humans and
    LLMs both produce the same 16-digit string.
    """
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(digits) != 16:
        logger.warning(
            "Captcha reply does not contain 16 digits (got %d): %r", len(digits), digits,
        )
        return None

    keypad_digits = digits[:10]
    captcha_digits = digits[10:]

    if len(set(keypad_digits)) != 10:
        logger.warning("Keypad digits not unique: %s", keypad_digits)
        return None

    digit_to_letter = {}
    for (letter, _), digit in zip(keypad, keypad_digits):
        digit_to_letter[digit] = letter

    try:
        return [digit_to_letter[d] for d in captcha_digits]
    except KeyError as e:
        logger.warning("Captcha digit %s not present in keypad", e)
        return None


class CaptchaSolver(ABC):
    """
    Abstract solver for CheckJC's verification page.

    The solver receives:
    - The distorted JPEG of the 6-digit captcha (anti-OCR).
    - The 10 small undistorted PNGs of the keypad buttons (one per digit
      0-9 shuffled into random data-value letters per session).

    The solver returns the **sequence of 6 letters** to click (in order)
    to enter the captcha into CheckJC's keypad — or ``None`` if it could
    not solve in time.

    Returning letters (not digits) lets the implementation own both halves
    of the puzzle: reading the distorted captcha AND identifying which
    digit each keypad button shows. That way:
    - The TelegramHumanSolver can ask the user once and get all 16 digits
      in a single reply.
    - A future LLMVisionSolver can solve everything with one vision call.
    - CheckJCClient stays simple: it just iterates the returned letters,
      re-reading the DOM between clicks to find each letter's current
      position (positions reshuffle after every click but letters do
      not).
    """

    @abstractmethod
    def solve(
        self,
        captcha_image_bytes: bytes,
        keypad: List[KeypadEntry],
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[List[str]]:
        """Return the 6-letter click sequence, or None on timeout/error."""
        raise NotImplementedError


class TelegramHumanSolver(CaptchaSolver):
    """
    Solver that asks the user to type the 6 digits via Telegram.

    Flow:

    1. Persist a ``PendingCaptcha`` row in state ``WAITING`` with the image.
    2. ``sendPhoto`` to the user's Telegram chat with the captcha as caption.
    3. Poll the DB row every ``poll_interval_seconds`` until it transitions
       to ``ANSWERED`` (bot wrote the user's reply) or ``EXPIRED`` (TTL hit).
    4. Return the 6-digit response, or None if the user did not reply in
       time.

    The bot listener (``checktime.bot.listener``) handles step (3) writes:
    when a user with a WAITING captcha sends a 6-digit message, the bot
    flips the row to ANSWERED with the value.
    """

    def __init__(
        self,
        telegram_client: Optional[TelegramClient] = None,
        poll_interval_seconds: float = 1.0,
    ):
        self.telegram = telegram_client or TelegramClient()
        self.poll_interval = poll_interval_seconds

    def solve(
        self,
        captcha_image_bytes: bytes,
        keypad: List[KeypadEntry],
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[List[str]]:
        if not user.telegram_chat_id:
            logger.warning(
                "User %s has no telegram_chat_id; cannot relay captcha",
                user.username,
            )
            return None
        if len(keypad) != 10:
            logger.error(
                "Expected 10 keypad buttons, got %d for user %s",
                len(keypad), user.username,
            )
            return None

        # Compose: captcha on top, keypad strip below, all in a single PNG.
        composite_png = compose_captcha_image(captcha_image_bytes, keypad)

        # Persist the pending row with the composite image so the user can
        # always re-fetch it if needed (we store what we actually sent).
        row = PendingCaptcha.create(
            user_id=user.id,
            check_type=check_type,
            image_bytes=composite_png,
            attempt=attempt,
            ttl_seconds=timeout_seconds,
        )
        logger.info(
            "Telegram captcha relay started for user %s (row=%d, attempt=%d, ttl=%ds)",
            user.username, row.id, attempt, timeout_seconds,
        )

        caption = self._build_caption(check_type, attempt, timeout_seconds)
        ok = self.telegram.send_photo(
            photo_bytes=composite_png,
            chat_id=user.telegram_chat_id,
            caption=caption,
            parse_mode="Markdown",
            filename=f"captcha_{user.username}_{row.id}.png",
        )
        if not ok:
            row.state = STATE_FAILED
            db.session.commit()
            logger.error("Failed to deliver captcha image to user %s", user.username)
            return None

        # Wait for the user to reply with 16 digits, then translate captcha
        # digits to keypad letters and return the click sequence.
        raw = self._wait_for_response(row.id, timeout_seconds, user)
        if raw is None:
            return None

        sequence = translate_16_digits_to_letters(raw, keypad)
        if sequence is None:
            # The user typed something we couldn't parse — tell them.
            try:
                self.telegram.send_message(
                    "Necesito *16 dígitos* en total: los 10 del teclado y los 6 del captcha. "
                    "Inténtalo otra vez con el próximo fichaje.",
                    chat_id=user.telegram_chat_id,
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        return sequence

    def _wait_for_response(
        self,
        row_id: int,
        timeout_seconds: int,
        user: User,
    ) -> Optional[str]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            time.sleep(self.poll_interval)
            db.session.expire_all()  # force fresh read of the row
            row = db.session.get(PendingCaptcha, row_id)
            if row is None:
                logger.warning("Captcha row %d disappeared mid-wait", row_id)
                return None
            if row.state == STATE_ANSWERED and row.response:
                response = row.response.strip()
                # Mark consumed so the bot won't try to answer it twice
                row.state = STATE_CONSUMED
                db.session.commit()
                logger.info(
                    "Got captcha reply from user %s (row=%d): %s",
                    user.username, row_id, response,
                )
                return response
            if row.state in (STATE_EXPIRED, STATE_FAILED):
                return None

        # Timed out — mark expired so the bot stops accepting late replies
        row = db.session.get(PendingCaptcha, row_id)
        if row and row.state == STATE_WAITING:
            row.state = STATE_EXPIRED
            db.session.commit()
        logger.info(
            "Captcha relay timed out for user %s (row=%d) after %ds",
            user.username, row_id, timeout_seconds,
        )
        # Notify the user so they understand why their fichaje was skipped
        try:
            self.telegram.send_message(
                f"⌛ Tiempo agotado: no recibí los 6 dígitos del captcha a tiempo. "
                f"Tu fichaje no se ha registrado automáticamente. "
                f"Ficha manualmente en checkjc.com cuando puedas.",
                chat_id=user.telegram_chat_id,
            )
        except Exception:
            pass
        return None

    @staticmethod
    def _build_caption(check_type: str, attempt: int, timeout_seconds: int) -> str:
        action = "entrada" if check_type == "in" else "salida"
        minutes = max(1, timeout_seconds // 60)
        suffix = "" if attempt == 1 else f" *(reintento {attempt})*"
        return (
            f"🧩 *Captcha para tu fichaje de {action}*{suffix}\n\n"
            f"Responde con *16 dígitos seguidos*: primero los *10 del teclado* "
            f"(de izquierda a derecha en el orden 1→10) y luego los *6 del "
            f"captcha*.\n\n"
            f"Ejemplo: si el teclado fuera 4 0 3 6 5 7 2 9 1 8 y el captcha "
            f"198142, responde `4036572918198142`.\n\n"
            f"⏱ Tienes {minutes} minutos."
        )


class LLMVisionSolver(CaptchaSolver):
    """
    Solver that asks Google Gemini to read the captcha automatically.

    Builds the same composite image (captcha + labelled 1..10 keypad)
    that the human solver sees, sends it to Gemini via the public REST
    API with a tight prompt, and expects back a single line of 16
    digits — same format the human would type. Then translates the 16
    digits to the 6-letter click sequence using the same helper as the
    Telegram solver.

    Falls back to None on any failure (HTTP error, malformed reply,
    timeout). The caller can chain this with TelegramHumanSolver as a
    fallback so a flaky Gemini call doesn't break a fichaje.

    The API key comes from each user's profile (User.google_api_key,
    encrypted at rest). The HTTP endpoint is the public Google AI
    Studio one — no Vertex/GCP project setup required.
    """

    # gemini-2.5-flash-lite is the cheapest model that still does this
    # task reliably on the free tier. gemini-2.5-flash also works but
    # only if we disable its "thinking" mode (see thinkingConfig below).
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    # Models shown in the user profile dropdown. The "*" models in the
    # comment are not in this list because they require a paid plan
    # (gemini-2.5-pro: free quota = 0) or are legacy-only as of March
    # 2026 (gemini-2.0-flash).
    SUPPORTED_MODELS = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",          # paid plan only
        "gemini-2.0-flash",        # legacy, existing customers only
    ]
    ENDPOINT_TMPL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent?key={key}"
    )
    PROMPT = (
        "You are reading a CheckJC verification page. The image has TWO "
        "parts stacked vertically:\n"
        "1. TOP: a distorted captcha with EXACTLY 6 digits.\n"
        "2. BOTTOM: a strip of 10 small clean buttons labelled 1..10 "
        "left to right. Each button shows ONE digit (0-9), each digit "
        "appearing exactly once across the 10 buttons.\n\n"
        "Reply with EXACTLY 16 digits and NOTHING else:\n"
        "- First the 10 keypad digits in order 1..10.\n"
        "- Then the 6 captcha digits in reading order.\n\n"
        "Do not add spaces, punctuation, words, or markdown. Just the "
        "16 raw digits."
    )

    def __init__(self, model: Optional[str] = None, http_timeout: int = 30):
        self.model = model or self.DEFAULT_MODEL
        self.http_timeout = http_timeout

    def solve(
        self,
        captcha_image_bytes: bytes,
        keypad: List[KeypadEntry],
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[List[str]]:
        api_key = getattr(user, "google_api_key", None)
        if not api_key:
            logger.info(
                "User %s has no Google API key configured; LLM solver cannot run",
                user.username,
            )
            return None
        if len(keypad) != 10:
            logger.error(
                "LLMVisionSolver: expected 10 keypad buttons, got %d", len(keypad),
            )
            return None

        # Per-user model preference wins over the solver-level default.
        model = getattr(user, "gemini_model", None) or self.model
        composite_png = compose_captcha_image(captcha_image_bytes, keypad)
        raw = self._ask_gemini(composite_png, api_key, model, user)
        if raw is None:
            return None
        sequence = translate_16_digits_to_letters(raw, keypad)
        if sequence is None:
            logger.warning(
                "Gemini reply did not parse to 16 valid digits for %s (raw=%r)",
                user.username, raw,
            )
            return None
        logger.info(
            "LLM solved captcha for user %s on attempt %d via %s",
            user.username, attempt, model,
        )
        return sequence

    def _ask_gemini(self, composite_png: bytes, api_key: str, model: str, user: User) -> Optional[str]:
        """Single Gemini call. Returns the raw text reply, or None on failure."""
        import base64 as _b64
        import requests

        url = self.ENDPOINT_TMPL.format(model=model, key=api_key)
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": self.PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": _b64.b64encode(composite_png).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                # 16 digits is ~10 output tokens. 64 leaves comfortable
                # headroom and is still cheap.
                "maxOutputTokens": 64,
                "candidateCount": 1,
                # Disable thinking on models that support it (2.5-flash).
                # Without this, 2.5-flash spends its output budget on
                # internal reasoning and returns a truncated reply.
                # 2.5-flash-lite, 2.5-pro, and 2.0-flash either don't
                # support this field or ignore it harmlessly.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        try:
            resp = requests.post(url, json=body, timeout=self.http_timeout)
        except Exception as exc:
            logger.warning("Gemini HTTP call failed for user %s: %s", user.username, exc)
            return None
        if resp.status_code != 200:
            logger.warning(
                "Gemini returned %d for user %s: %s",
                resp.status_code, user.username, resp.text[:200],
            )
            return None
        try:
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                logger.warning("Gemini returned no candidates for user %s: %s",
                               user.username, data)
                return None
            parts = candidates[0].get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts).strip()
            return text or None
        except Exception as exc:
            logger.warning("Failed to parse Gemini response for %s: %s", user.username, exc)
            return None


class HybridCaptchaSolver(CaptchaSolver):
    """
    Try the LLM first; if it returns None, fall back to the Telegram
    human solver.

    This is what the scheduler wires in by default: users with an API
    key get automatic resolution, users without one fall through to the
    Telegram flow, and if Gemini is flaky / over quota the user still
    gets a Telegram prompt as a safety net.
    """

    def __init__(self, llm: "LLMVisionSolver", telegram: "TelegramHumanSolver"):
        self.llm = llm
        self.telegram = telegram

    def solve(
        self,
        captcha_image_bytes: bytes,
        keypad: List[KeypadEntry],
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[List[str]]:
        if getattr(user, "google_api_key", None):
            sequence = self.llm.solve(
                captcha_image_bytes, keypad, user, check_type, attempt, timeout_seconds,
            )
            if sequence is not None:
                return sequence
            logger.info(
                "LLM solver failed for user %s; falling back to Telegram human",
                user.username,
            )
        return self.telegram.solve(
            captcha_image_bytes, keypad, user, check_type, attempt, timeout_seconds,
        )


def cleanup_expired_captchas() -> int:
    """
    Mark stale WAITING rows as EXPIRED. Called periodically by the bot.

    Returns the number of rows transitioned. Safe to call concurrently —
    only rows past their expires_at are touched.
    """
    now = datetime.now()
    stale = PendingCaptcha.query.filter(
        PendingCaptcha.state == STATE_WAITING,
        PendingCaptcha.expires_at < now,
    ).all()
    for row in stale:
        row.state = STATE_EXPIRED
    if stale:
        db.session.commit()
        logger.info("Expired %d stale captcha rows", len(stale))
    return len(stale)

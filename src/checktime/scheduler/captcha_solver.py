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

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

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


class CaptchaSolver(ABC):
    """
    Abstract solver for CheckJC's 6-digit verification captcha.

    Implementations get the raw distorted image (JPEG bytes) and return the
    decoded 6-digit string, or ``None`` if they could not solve it in time.

    Implementations MUST NOT touch the keypad mapping (data-value letters)
    — they only decode the distorted image into a 6-digit string. The
    caller is responsible for mapping digits to the right buttons.
    """

    @abstractmethod
    def solve(
        self,
        captcha_image_bytes: bytes,
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[str]:
        """Return the 6-digit captcha as a string, or None on timeout/error."""
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
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[str]:
        if not user.telegram_chat_id:
            logger.warning(
                "User %s has no telegram_chat_id; cannot relay captcha",
                user.username,
            )
            return None

        # Step 1: persist the pending row
        row = PendingCaptcha.create(
            user_id=user.id,
            check_type=check_type,
            image_bytes=captcha_image_bytes,
            attempt=attempt,
            ttl_seconds=timeout_seconds,
        )
        logger.info(
            "Telegram captcha relay started for user %s (row=%d, attempt=%d, ttl=%ds)",
            user.username, row.id, attempt, timeout_seconds,
        )

        # Step 2: ship the image to the user
        caption = self._build_caption(check_type, attempt, timeout_seconds)
        ok = self.telegram.send_photo(
            photo_bytes=captcha_image_bytes,
            chat_id=user.telegram_chat_id,
            caption=caption,
            parse_mode="Markdown",
            filename=f"captcha_{user.username}_{row.id}.jpg",
        )
        if not ok:
            row.state = STATE_FAILED
            db.session.commit()
            logger.error("Failed to deliver captcha image to user %s", user.username)
            return None

        # Step 3: poll the DB until the row changes state or expires
        return self._wait_for_response(row.id, timeout_seconds, user)

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
            f"Responde con los *6 dígitos* de la imagen para que registre tu "
            f"fichaje.\n\n"
            f"⏱ Tienes {minutes} minutos."
        )


class LLMVisionSolver(CaptchaSolver):
    """
    Placeholder for a future solver that asks an LLM with vision to read
    the distorted captcha.

    Not wired up yet: instantiating it raises NotImplementedError on solve().
    Plug in a real implementation in v1.9+ — the rest of the code only
    depends on the abstract CaptchaSolver contract.

    Suggested implementation when picking this up:
    - Accept an Anthropic / OpenAI / Gemini client in the constructor.
    - Encode captcha_image_bytes as base64 and send with a tight prompt
      ("Reply ONLY with the 6 digits visible. No other text.").
    - Validate the response is 6 numeric chars; retry once if not.
    - Optionally fall back to TelegramHumanSolver on ambiguous responses.
    """

    def __init__(self, *args, **kwargs):
        # Keep constructor signature flexible; concrete impls will define
        # what client/credentials they need.
        self._args = args
        self._kwargs = kwargs

    def solve(
        self,
        captcha_image_bytes: bytes,
        user: User,
        check_type: str,
        attempt: int = 1,
        timeout_seconds: int = 300,
    ) -> Optional[str]:
        raise NotImplementedError(
            "LLMVisionSolver is a placeholder. Wire up an LLM client and "
            "implement the vision call before using it."
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

#!/usr/bin/env python3
"""
Manual end-to-end test for LLMVisionSolver against a real composite
captcha image.

Use this while account 47779708z is locked (or whenever the auto flow
isn't reachable) to confirm that Gemini reads the captcha correctly
with a given API key + model.

Usage:
    # Preferred: pass the key via env var so it never ends up in shell
    # history or scrollback.
    export GEMINI_API_KEY=...
    python tests/debug_gemini_solver.py --image /path/to/composite.png

    # Alternative (less safe — leaks into bash history):
    python tests/debug_gemini_solver.py \\
        --api-key YOUR_GEMINI_API_KEY \\
        --image /path/to/composite.png

    # Override the model:
    python tests/debug_gemini_solver.py \\
        --image composite.png \\
        --model gemini-2.5-pro

The image must already be a composite produced by
``compose_captcha_image`` (captcha on top, keypad 1→10 below). Easiest
way to get one in production: copy the JPEG sent via Telegram for the
last fichaje attempt, or take a screenshot of /portal/employee/verification
and paste it in.

The script reproduces the exact prompt and request body that
``LLMVisionSolver`` uses, so a green result here means the wired-up
solver will also work.
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests

# Same prompt as in checktime/scheduler/captcha_solver.py
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

ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)


def detect_mime(image_bytes: bytes) -> str:
    """Return the MIME type by magic bytes. Production always sends PNG
    (the composite is built with PIL), but ad-hoc tests may pass a JPG
    they copied from Telegram or a screenshot."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"GIF8"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    # Fallback to PNG — Gemini sometimes accepts it anyway.
    return "image/png"


def call_gemini(api_key: str, model: str, image_bytes: bytes, timeout: int = 30):
    url = ENDPOINT.format(model=model, key=api_key)
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": detect_mime(image_bytes),
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 64,
            "candidateCount": 1,
            # 2.5-flash is a "thinking model"; without this it spends
            # its output budget thinking and returns a truncated reply.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    resp = requests.post(url, json=body, timeout=timeout)
    return resp


def parse_reply(raw: str):
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) != 16:
        return None, None, f"Expected 16 digits, got {len(digits)}: {digits!r}"
    keypad = digits[:10]
    captcha = digits[10:]
    if len(set(keypad)) != 10:
        return keypad, captcha, "Keypad digits are not unique (0-9 must each appear once)"
    for d in captcha:
        if d not in keypad:
            return keypad, captcha, f"Captcha digit {d} is not in the keypad"
    return keypad, captcha, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key (defaults to $GEMINI_API_KEY; preferred over CLI "
             "so the key doesn't leak into shell history)",
    )
    parser.add_argument("--image", required=True, help="Path to the composite PNG")
    parser.add_argument(
        "--model", default="gemini-2.5-flash-lite",
        help="Gemini model id (default: gemini-2.5-flash-lite)",
    )
    args = parser.parse_args(argv)

    if not args.api_key:
        print(
            "ERROR: no API key provided. Set $GEMINI_API_KEY or pass --api-key.",
            file=sys.stderr,
        )
        return 1

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        return 1

    image_bytes = image_path.read_bytes()
    print(f"Loaded image: {image_path} ({len(image_bytes)} bytes)")
    print(f"Calling {args.model}...")

    try:
        resp = call_gemini(args.api_key, args.model, image_bytes)
    except Exception as exc:
        print(f"ERROR: HTTP call failed: {exc}", file=sys.stderr)
        return 2

    if resp.status_code != 200:
        print(f"ERROR: Gemini returned HTTP {resp.status_code}")
        print("Body:", resp.text[:600])
        return 3

    data = resp.json()
    try:
        text = "".join(
            p.get("text", "")
            for p in data["candidates"][0]["content"]["parts"]
        ).strip()
    except (KeyError, IndexError):
        print("ERROR: unexpected response shape")
        print(json.dumps(data, indent=2))
        return 4

    print("Raw reply:", repr(text))
    keypad, captcha, err = parse_reply(text)
    if err:
        print(f"PARSE ERROR: {err}")
        if keypad:
            print(f"  keypad digits: {keypad}")
        if captcha:
            print(f"  captcha digits: {captcha}")
        return 5

    print(f"Keypad  (positions 1..10): {' '.join(keypad)}")
    print(f"Captcha (6 digits):        {captcha}")
    print(f"Click sequence by keypad index:")
    for d in captcha:
        idx = keypad.index(d) + 1
        print(f"  digit {d} → position {idx}")
    print()
    print("SUCCESS: Gemini returned a well-formed 16-digit reply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

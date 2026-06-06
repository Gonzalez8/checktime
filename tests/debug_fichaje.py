#!/usr/bin/env python3
"""
Manual end-to-end fichaje test that mirrors the scheduler's path
for a single user, on demand.

Use this to validate the v1.10.x anti-detection changes against a
real CheckJC session without waiting for the scheduled minute. The
real check WILL be recorded in CheckJC — don't run it on a holiday
or you'll have to explain a phantom entry/exit to HR.

Designed to run INSIDE the running container, because the DB host
is "db" (Docker network DNS) and the env vars come from stack.env:

    docker exec -it checktime-app python /app/tests/debug_fichaje.py <username> in
    docker exec -it checktime-app python /app/tests/debug_fichaje.py <username> out

Skips, vs the scheduler:
- is_working_day() (so it works any time)
- The per-user schedule jitter (schedule_check) — not relevant for a
  one-off manual call

Keeps:
- Real CheckJCClient with all v1.10.x anti-detection (UA, stealth
  init script, human keystrokes, mouse warmup, lite-variant cap)
- HybridCaptchaSolver (Gemini → Telegram fallback) so a /verification
  page still gets resolved
- Post-login human pause (20-90s by default) — set --no-jitter to
  skip ONLY if you're sure
"""

import argparse
import logging
import random
import sys
import time

# Allow running from anywhere inside the container (PYTHONPATH=/app).
sys.path.insert(0, "/app/src")

from checktime.scheduler.captcha_solver import (  # noqa: E402
    HybridCaptchaSolver,
    LLMVisionSolver,
    TelegramHumanSolver,
)
from checktime.scheduler.checker import CheckJCClient  # noqa: E402
from checktime.shared.config import (  # noqa: E402
    get_post_login_jitter_max_seconds,
    get_post_login_jitter_min_seconds,
)
from checktime.shared.services.user_manager import UserManager  # noqa: E402
from checktime.utils.telegram import TelegramClient  # noqa: E402
from checktime.web import create_app  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("username", help="CheckTime username (the one in the web UI, NOT the CheckJC one)")
    parser.add_argument("check_type", choices=["in", "out"], help="'in' for entrada, 'out' for salida")
    parser.add_argument(
        "--no-jitter", action="store_true",
        help="Skip the post-login 20-90s pause. Use only if you know what you're doing — "
             "the pause is one of the main mitigations against anti-bot / IDS pattern matching.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_app()
    with app.app_context():
        user = UserManager().get_by_username(args.username)
        if user is None:
            print(f"ERROR: CheckTime user {args.username!r} not found", file=sys.stderr)
            return 1
        if not user.checkjc_username or not user.checkjc_password or not user.checkjc_subdomain:
            print(
                f"ERROR: CheckTime user {args.username!r} has no CheckJC credentials configured",
                file=sys.stderr,
            )
            return 1

        print("--- Manual fichaje test ---")
        print(f"CheckTime user: {user.username} (id={user.id})")
        print(f"CheckJC user:   {user.checkjc_username}@{user.checkjc_subdomain}")
        print(f"Check type:     {args.check_type}")
        print(f"Jitter:         {'OFF (--no-jitter)' if args.no_jitter else 'ON'}")
        print()

        captcha_solver = HybridCaptchaSolver(
            llm=LLMVisionSolver(),
            telegram=TelegramHumanSolver(telegram_client=TelegramClient()),
        )

        try:
            with CheckJCClient(
                username=user.checkjc_username,
                password=user.checkjc_password,
                subdomain=user.checkjc_subdomain,
                captcha_solver=captcha_solver,
                user=user,
                check_type=args.check_type,
            ) as client:
                print(">>> login()")
                t0 = time.monotonic()
                client.login()
                print(f"    login OK ({time.monotonic() - t0:.1f}s)")

                if not args.no_jitter:
                    jmin = max(0, get_post_login_jitter_min_seconds())
                    jmax = max(jmin, get_post_login_jitter_max_seconds())
                    pause = random.uniform(jmin, jmax)
                    print(f">>> sleeping {pause:.1f}s (post-login human pause)")
                    time.sleep(pause)

                print(f">>> check_{args.check_type}()")
                t1 = time.monotonic()
                if args.check_type == "in":
                    client.check_in()
                else:
                    client.check_out()
                print(f"    check OK ({time.monotonic() - t1:.1f}s)")
                print()
                print("SUCCESS — fichaje registered in CheckJC")
                return 0
        except Exception as exc:
            print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())

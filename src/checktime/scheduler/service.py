#!/usr/bin/env python
"""
Scheduler service for CheckTime application.
This script starts the scheduler service that checks schedules and performs scheduled clock-ins/outs for all users.
"""

import hashlib
import logging
import random
import schedule
import time
from datetime import datetime
import threading
import concurrent.futures

from checktime.scheduler.checker import (
    CheckJCAccountLocked,
    CheckJCCaptchaFailed,
    CheckJCClient,
    CheckJCIPBlocked,
    CheckJCLoginRejected,
    CheckJCSessionLost,
    CheckJCFormError,
    CheckJCUnexpectedResponse,
)
from checktime.scheduler.captcha_solver import (
    HybridCaptchaSolver,
    LLMVisionSolver,
    TelegramHumanSolver,
)
from checktime.shared.repository.day_override_repository import DayOverrideRepository
from checktime.shared.config import (
    get_log_level,
    get_post_login_jitter_max_seconds,
    get_post_login_jitter_min_seconds,
    get_schedule_jitter_seconds,
    get_schedule_random_offset_minutes,
    get_user_check_stagger_seconds,
)
from checktime.utils.telegram import TelegramClient
from checktime.shared.services.holiday_manager import HolidayManager
from checktime.shared.services.user_manager import UserManager
from checktime.shared.services.schedule_manager import ScheduleManager
from checktime.web import create_app

# Configure logging.
# IMPORTANT: force=True garantiza que estos handlers se apliquen aunque
# alguno de los imports previos (Flask / extensiones) ya haya tocado el
# root logger. Sin force=True, basicConfig se ignora silenciosamente y
# logger.error() acaba en /dev/null (lo que explicaba que los errores
# llegasen a Telegram pero no apareciesen en `docker logs` ni en el fichero).
logging.basicConfig(
    level=getattr(logging, get_log_level()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/checktime/scheduler.log"),
        logging.StreamHandler()
    ],
    force=True,
)
logger = logging.getLogger(__name__)


def _format_error_for_telegram(check_type, username, exc):
    """Construye un mensaje claro para Telegram según el tipo de excepción.
    Mantiene la traza para el log de fichero, pero solo manda al usuario lo
    accionable."""
    exc_name = type(exc).__name__
    base = f"Check {check_type} for {username}"

    if isinstance(exc, CheckJCAccountLocked):
        return (
            f"⛔ {base}: tu cuenta de CheckJC está BLOQUEADA. "
            f"{exc} Pide al admin/supervisor de CheckJC que la desbloquee y "
            f"desactiva el auto-checkin en CheckTime mientras tanto."
        )
    if isinstance(exc, CheckJCIPBlocked):
        return f"🚫 {base}: {exc}"
    if isinstance(exc, CheckJCLoginRejected):
        return (
            f"🚧 {base}: CheckJC rechazó el login. "
            f"Puede ser credenciales mal escritas o un rate-limit silencioso del IP "
            f"(intentos seguidos antes del bloqueo duro). "
            f"Confirma haciendo login manual en la web."
        )
    if isinstance(exc, CheckJCSessionLost):
        return f"⏳ {base}: sesión perdida durante el fichaje. Reintentará en el próximo ciclo."
    if isinstance(exc, CheckJCCaptchaFailed):
        return (
            f"🧩 {base}: no se pudo resolver el captcha de verificación. "
            f"Ficha manualmente en checkjc.com."
        )
    if isinstance(exc, CheckJCFormError):
        return f"🧩 {base}: CheckJC cambió el HTML — los selectores ya no casan. Requiere actualización del checker."
    if isinstance(exc, CheckJCUnexpectedResponse):
        return f"❓ {base}: respuesta HTTP inesperada de CheckJC ({exc})."
    # Cualquier otro tipo (timeout de red, error Playwright, etc.)
    return f"❌ {base}: {exc_name}: {exc}"

# Initialize Telegram client
telegram_client = TelegramClient()

# Initialize service managers
user_manager = UserManager()
schedule_manager = ScheduleManager()

# Create Flask app
app = create_app()

def _user_label(user_id, username=None):
    """Format the user identifier for log messages: prefer username, fall
    back to id. Keeps logs readable when the caller has the User object
    (almost always) without changing the public signature of helpers
    that are still called with just an id."""
    if username:
        return f"user {username} (id={user_id})"
    return f"user_id={user_id}"


# user_id -> (date, check_in_time, check_out_time) of the last schedule
# preview we logged for this user. We re-emit the preview whenever the
# tuple changes: new day, OR same day but the configured times moved
# (e.g., the operator added an override at 18:00 for a 19:00 fichaje).
# One entry per user max — replaces on change, never grows unbounded.
_schedule_preview_logged_for = {}


def is_working_day(user_id=None, username=None):
    """
    Check if today is a working day for a specific user.

    Args:
        user_id (int, optional): The user ID to check. If None, checks globally.
        username (str, optional): Username for log readability — does not
            affect the lookup, only the log lines.

    Returns:
        bool: True if it's a working day, False otherwise.
    """
    with app.app_context():
        today = datetime.now().date()
        weekday = today.weekday()
        label = _user_label(user_id, username)

        # Check if it's a holiday for this user using HolidayManager
        holiday_manager = HolidayManager(user_id)
        date_str = today.strftime('%Y-%m-%d')
        holidays = holiday_manager.load_holidays(user_id)

        if date_str in holidays:
            logger.info(f"Holiday found in database for {label}: {today}")
            return False

        # A DayOverride for today UNLOCKS the day as a fichaje day, even
        # if the regular schedule wouldn't fire. This matches the user's
        # mental model: "if I created an override, I want fichaje today
        # regardless of weekday/period setup". Holidays still win above
        # (legal holiday > override). Override can be deleted or updated
        # mid-day — the scheduler picks up the change on the next minute
        # tick because it re-reads override + schedule every iteration.
        if user_id is not None:
            override = DayOverrideRepository().get_by_user_and_date(user_id, today)
            if override:
                logger.info(
                    f"Day override active for {label}: {today} → "
                    f"working day ({override.check_in_time} - {override.check_out_time})"
                )
                return True

        # Check if there's a schedule for today for this user using ScheduleManager
        active_period = schedule_manager.get_active_period_for_date(today, user_id)
        if not active_period:
            logger.info(f"No active period for today: {today} for {label}")
            return False

        # Check if there's a schedule configured for this day of the week
        day_schedule = schedule_manager.get_day_schedule(active_period.id, weekday)
        if not day_schedule:
            logger.info(f"No schedule configured for today (weekday={weekday}): {today} for {label}")
            return False

        logger.info(f"Today is a working day: {today} for {label}")
        return True

def get_schedule_times(user_id, username=None):
    """
    Get check-in and check-out times based on the current schedule in database for a specific user.

    Args:
        user_id (int): The user ID to get schedule for.
        username (str, optional): Username for log readability — does not
            affect the lookup, only the log lines.

    Returns:
        tuple: (check_in_time, check_out_time) or (None, None) if no schedule.
    """
    with app.app_context():
        today = datetime.now().date()
        label = _user_label(user_id, username)

        # Get schedule times for today using ScheduleManager
        check_in_time, check_out_time = schedule_manager.get_schedule_times_for_date(today, user_id)

        if check_in_time and check_out_time:
            logger.info(f"Using schedule from database for {label}: {check_in_time} - {check_out_time}")
            return check_in_time, check_out_time

        # If no configuration in the database, don't clock
        logger.info(f"No schedule configured in the database for {label}. Automatic clock in/out will not be performed.")
        return None, None

def perform_check_for_user(user, check_type):
    """
    Perform the check-in/out process for a specific user.
    
    Args:
        user (User): The user to perform check for.
        check_type (str): Type of check ('in' or 'out')
    """
    if not is_working_day(user.id, user.username):
        message = f"Today is not a working day or it's a holiday for user {user.username}. No check will be performed."
        logger.info(message)
        return

    logger.info(f"Starting {check_type} check process for user {user.username}...")

    # The captcha solver hits the DB (PendingCaptcha) and the bot listener
    # polls the same rows from another process. Both need an active Flask
    # app context for db.session to resolve. Wrap the whole fichaje in one.
    with app.app_context():
        try:
            # Hybrid solver: try Gemini first if the user has an API key,
            # otherwise (or on LLM failure) fall through to the Telegram
            # human relay. TelegramHumanSolver is unchanged and remains
            # the safety net so today's working flow stays intact.
            captcha_solver = HybridCaptchaSolver(
                llm=LLMVisionSolver(),
                telegram=TelegramHumanSolver(telegram_client=telegram_client),
            )
            with CheckJCClient(
                username=user.checkjc_username,
                password=user.checkjc_password,
                subdomain=user.checkjc_subdomain,
                captcha_solver=captcha_solver,
                user=user,
                check_type=check_type,
            ) as client:
                client.login()
                # Human-think pause between login and fichaje. Firing the
                # check 1-2s after login every single day is a textbook bot
                # fingerprint for anti-bot / IDS systems. A random 20-90s
                # pause makes the pattern
                # indistinguishable from a real user landing on the
                # dashboard and clicking after a moment.
                jitter_min = max(0, get_post_login_jitter_min_seconds())
                jitter_max = max(jitter_min, get_post_login_jitter_max_seconds())
                if jitter_max > 0:
                    pause_s = random.uniform(jitter_min, jitter_max)
                    logger.info(
                        "Post-login human pause for %s: sleeping %.1fs "
                        "before fichaje", user.username, pause_s,
                    )
                    time.sleep(pause_s)
                if check_type == "in":
                    client.check_in()
                    icon = "🟢"
                else:
                    client.check_out()
                    icon = "🔴"
                logger.info(f"{check_type.capitalize()} check completed successfully for user {user.username}.")
                if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id:
                    if (hasattr(user, 'telegram_chat_id') and user.telegram_chat_id and getattr(user, 'telegram_notifications_enabled', False)):
                        telegram_client.send_message(f"{icon} Check {check_type} completed successfully", chat_id=user.telegram_chat_id)
        except Exception as e:
            # logger.exception incluye el traceback completo: tipo de excepción,
            # mensaje y línea exacta donde se lanzó. Va al fichero y a stdout.
            logger.exception(
                "Error during check %s for user %s (%s)",
                check_type, user.username, type(e).__name__,
            )
            telegram_msg = _format_error_for_telegram(check_type, user.username, e)
            if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id and getattr(user, 'telegram_notifications_enabled', False):
                # parse_mode=None: error messages may contain URLs or dots
                # that Telegram's Markdown parser rejects with 400.
                telegram_client.send_message(
                    telegram_msg, chat_id=user.telegram_chat_id, parse_mode=None,
                )

def _effective_time_for_today(user_id, configured_time, check_type, today, max_offset_min):
    """Deterministically offset the configured HH:MM by ±max_offset_min
    for (user_id, today, check_type).

    Deterministic so within a single day the answer is stable: the
    minute-tick scheduler can match it once and only once, no double
    fires, no missed minutes. The seed is internal to the app, so an
    external IDS can't predict tomorrow's actual time from today's.

    Returns 'HH:MM'. Clamped to [00:00, 23:59] so an early-morning or
    late-night fichaje doesn't roll into the next/previous day.
    """
    if max_offset_min <= 0 or not configured_time:
        return configured_time
    seed_input = f"{user_id}-{today.isoformat()}-{check_type}-{configured_time}"
    h = hashlib.sha256(seed_input.encode("utf-8")).digest()
    seed_int = int.from_bytes(h[:4], "big")
    rng = random.Random(seed_int)
    offset = rng.randint(-max_offset_min, max_offset_min)
    hh, mm = configured_time.split(":")
    base_minutes = int(hh) * 60 + int(mm)
    new_minutes = max(0, min(1439, base_minutes + offset))
    return f"{new_minutes // 60:02d}:{new_minutes % 60:02d}"


def get_users_to_check_now():
    """
    Returns a list of (user, check_type) tuples for users who need to check in or out at the current time.
    """
    with app.app_context():
        users = user_manager.get_all_with_checkjc_configured()
    if not users:
        return []

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    today = now.date()
    max_offset = get_schedule_random_offset_minutes()
    users_to_check = []

    for user in users:
        if not is_working_day(user.id, user.username):
            continue
        check_in_time, check_out_time = get_schedule_times(user.id, user.username)
        if check_in_time is None or check_out_time is None:
            continue
        # Apply per-day deterministic ±N minute offset to the configured
        # time. Mitigates the always-HH:MM:00 pattern that anti-bot / IDS
        # systems flag as automation.
        eff_in = _effective_time_for_today(user.id, check_in_time, "in", today, max_offset)
        eff_out = _effective_time_for_today(user.id, check_out_time, "out", today, max_offset)

        # Emit a preview at INFO so the operator sees exactly when the
        # fichaje will happen today without waiting for the fire-time
        # log or computing the offset by hand. Re-emitted whenever the
        # tuple (date, check_in_time, check_out_time) changes — so a
        # mid-day override that moves the configured time triggers a
        # fresh announcement, not silence.
        preview_value = (today, check_in_time, check_out_time)
        if _schedule_preview_logged_for.get(user.id) != preview_value:
            def _offset_min(configured, effective):
                ch, cm = (int(x) for x in configured.split(":"))
                eh, em = (int(x) for x in effective.split(":"))
                return (eh * 60 + em) - (ch * 60 + cm)
            previous = _schedule_preview_logged_for.get(user.id)
            change_reason = "first time today" if previous is None or previous[0] != today \
                else "schedule changed mid-day"
            logger.info(
                "Today's schedule for user %s (id=%d) — %s: "
                "IN configured=%s effective=%s (%+dmin), "
                "OUT configured=%s effective=%s (%+dmin)",
                user.username, user.id, change_reason,
                check_in_time, eff_in, _offset_min(check_in_time, eff_in),
                check_out_time, eff_out, _offset_min(check_out_time, eff_out),
            )
            _schedule_preview_logged_for[user.id] = preview_value

        if current_time == eff_in:
            logger.info(
                "User %s: fichaje IN due now (configured=%s, effective=%s, offset=%+dmin)",
                user.username, check_in_time, eff_in,
                int(eff_in.split(":")[0]) * 60 + int(eff_in.split(":")[1])
                - (int(check_in_time.split(":")[0]) * 60 + int(check_in_time.split(":")[1])),
            )
            users_to_check.append((user, "in"))
        elif current_time == eff_out:
            logger.info(
                "User %s: fichaje OUT due now (configured=%s, effective=%s, offset=%+dmin)",
                user.username, check_out_time, eff_out,
                int(eff_out.split(":")[0]) * 60 + int(eff_out.split(":")[1])
                - (int(check_out_time.split(":")[0]) * 60 + int(check_out_time.split(":")[1])),
            )
            users_to_check.append((user, "out"))
    return users_to_check

def schedule_check():
    """Check if it's time to perform check-in/out based on schedules for all users, and do it sequentially."""
    users_to_check = get_users_to_check_now()
    # CheckJC anti-bot serves a stripped 'lite' page when several logins
    # arrive from the same egress IP within seconds. Space users out.
    stagger_seconds = get_user_check_stagger_seconds()
    # Per-firing schedule jitter so the run does NOT begin at HH:MM:00.
    # Anti-bot / IDS systems flag an always-09:00:XX cadence as a bot
    # signal; adding 0-30s of random delay breaks that pattern without
    # affecting attendance accuracy.
    jitter_max = max(0, get_schedule_jitter_seconds())
    for index, (user, check_type) in enumerate(users_to_check):
        if index > 0 and stagger_seconds > 0:
            logger.info(
                "Sleeping %ds before next user to avoid CheckJC anti-bot",
                stagger_seconds,
            )
            time.sleep(stagger_seconds)
        if jitter_max > 0:
            jitter_s = random.uniform(0, jitter_max)
            logger.info(
                "Schedule jitter for %s: sleeping %.1fs to desync HH:MM:00",
                user.username, jitter_s,
            )
            time.sleep(jitter_s)
        perform_check_for_user(user, check_type)

def perform_check_in():
    """Perform the check-in process for all eligible users."""
    perform_check("in")

def perform_check_out():
    """Perform the check-out process for all eligible users."""
    perform_check("out")

def main():
    """Main function that runs only the scheduler service."""
    logger.info("Starting automatic check-in/out service for all users...")
    
    try:
        # Initialize app context once at startup
        with app.app_context():
            # Send message inside the app context 
            telegram_client.send_message("🚀 Starting automatic check-in/out service for all users")

        # Schedule tasks with dynamic schedules
        schedule.every().minute.do(lambda: schedule_check())

        # Keep the script running
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                error_msg = f"Error in main loop: {str(e)}"
                logger.error(error_msg)
                with app.app_context():
                    telegram_client.send_message(f"❌ {error_msg}")
                time.sleep(300)  # Wait 5 minutes before retrying
    except Exception as e:
        logger.error(f"Fatal error in scheduler service: {str(e)}")
        # Try to send error notification with app context
        try:
            with app.app_context():
                # Mensaje a la cuenta general, no específico de un usuario
                telegram_client.send_message(f"💥 Fatal error in scheduler service: {str(e)}")
        except:
            logger.error("Could not send error notification")

if __name__ == "__main__":
    main() 
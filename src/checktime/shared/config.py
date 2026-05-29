"""
Centralized configuration management for CheckTime.
"""

import os
from typing import Any, Dict, Optional

# Cache for configuration values
_config_cache: Dict[str, Any] = {}

def get_config(key: str, default: Optional[Any] = None) -> Any:
    """
    Get a configuration value from environment variables.
    
    Args:
        key: The configuration key
        default: Default value if key is not found
    
    Returns:
        The configuration value
    """
    if key in _config_cache:
        return _config_cache[key]
    
    value = os.getenv(key, default)
    _config_cache[key] = value
    return value

# Database configuration
def get_database_url() -> str:
    """Get the database URL from configuration"""
    # Sino, construirlo a partir de los componentes
    user = get_postgres_user()
    password = get_postgres_password()
    db_name = get_postgres_db()
    host = 'db'
    port = get_config('POSTGRES_DB_PORT', '5432')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

def get_database_storage_path() -> str:
    """Get the database storage path for Docker volume"""
    return get_config('DB_STORAGE_PATH', 'postgres_data')

def get_postgres_user() -> str:
    """Get the PostgreSQL username"""
    return get_config('POSTGRES_USER', 'postgres')

def get_postgres_password() -> str:
    """Get the PostgreSQL password"""
    return get_config('POSTGRES_PASSWORD', 'postgres')

def get_postgres_db() -> str:
    """Get the PostgreSQL database name"""
    return get_config('POSTGRES_DB', 'checktime')

# Web server configuration
def get_secret_key() -> str:
    """Get the Flask secret key"""
    return get_config('FLASK_SECRET_KEY', 'dev')

def get_admin_password() -> str:
    """Get the admin password"""
    return get_config('ADMIN_PASSWORD', 'admin')

def get_port() -> int:
    """Get the web server port"""
    return int(get_config('PORT', '5000'))

# Telegram configuration
def get_telegram_token() -> str:
    """Get the Telegram bot token"""
    return get_config('TELEGRAM_BOT_TOKEN', '')

def get_telegram_chat_id() -> str:
    """Get the Telegram chat ID"""
    return get_config('TELEGRAM_CHAT_ID', '')

def get_telegram_bot_name() -> str:
    """Get the Telegram bot name"""
    return get_config('TELEGRAM_BOT_NAME', '@CheckTimeBot')

# Selenium configuration
def get_selenium_timeout() -> int:
    """Get the Selenium timeout in seconds"""
    return int(get_config('SELENIUM_TIMEOUT', '30'))

# Scheduler configuration
def get_user_check_stagger_seconds() -> int:
    """Seconds to wait between consecutive users in the same scheduler batch.

    CheckJC's anti-bot rejects rapid sequential logins from the same egress
    IP (it serves a stripped 'lite' HTML variant where Stencil never
    hydrates). Spacing logins out avoids that penalty.
    """
    return int(get_config('USER_CHECK_STAGGER_SECONDS', '60'))

def get_checkjc_lite_retries() -> int:
    """Extra attempts to retry login when CheckJC serves the 'lite' variant.

    Defaults to 0: NO retry. After the InfoJC May 2026 lockout report
    flagged "multiple consecutive /login requests" as one of the reasons
    for the account ban, the operator explicitly opted for zero retries.
    The hard cap at 2 in code stays as a belt-and-braces guard in case
    someone raises this in stack.env without thinking it through.

    Trade-off: if CheckJC serves the lite anti-bot variant on the only
    attempt, the fichaje fails for that minute — but no second /login
    GET happens, and no second submit ever could.
    """
    return int(get_config('CHECKJC_LITE_RETRIES', '0'))

def get_checkjc_lite_retry_seconds() -> int:
    """Base seconds to wait between lite-variant retries.

    The actual wait is base * 2^(attempt-1) + random jitter, so the
    second retry (if you raise CHECKJC_LITE_RETRIES > 1) waits at least
    twice as long as the first. Default 60.
    """
    return int(get_config('CHECKJC_LITE_RETRY_SECONDS', '60'))

# Anti-detection / humanization
def get_schedule_jitter_seconds() -> int:
    """Random seconds in [0, X) to delay the per-user fichaje after the
    minute trigger fires.

    Without this, every user fires at exactly HH:MM:00 (modulo the
    inter-user stagger), which is the cron-perfect fingerprint that
    InfoJC's IDS flagged. Default 30. Set to 0 to disable.
    """
    return int(get_config('CHECKJC_SCHEDULE_JITTER_SECONDS', '30'))

def get_post_login_jitter_min_seconds() -> int:
    """Lower bound (inclusive) of the human-think pause between a
    successful login and the actual fichaje click. Default 20.

    The InfoJC report listed our previous behavior (login + fichaje
    within 1-2 seconds, every day) as a top anomaly. Anything from
    ~20s upward is plausible "user landed and clicked".
    """
    return int(get_config('CHECKJC_POST_LOGIN_JITTER_MIN_SECONDS', '20'))

def get_post_login_jitter_max_seconds() -> int:
    """Upper bound (inclusive) of the human-think pause. Default 90."""
    return int(get_config('CHECKJC_POST_LOGIN_JITTER_MAX_SECONDS', '90'))

def get_keystroke_delay_min_ms() -> int:
    """Minimum per-character delay when typing username/password.
    Default 60ms — fast typist territory."""
    return int(get_config('CHECKJC_KEYSTROKE_DELAY_MIN_MS', '60'))

def get_keystroke_delay_max_ms() -> int:
    """Maximum per-character delay when typing. Default 180ms."""
    return int(get_config('CHECKJC_KEYSTROKE_DELAY_MAX_MS', '180'))

# Logging configuration
def get_log_level() -> str:
    """Get the logging level"""
    return get_config('LOG_LEVEL', 'INFO')

def get_log_date_format() -> str:
    """Get the log date format"""
    return get_config('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')

def get_simulation_mode() -> bool:
    """Get the simulation mode from environment variables."""
    return os.getenv("SIMULATION_MODE", "false").lower() == "true"
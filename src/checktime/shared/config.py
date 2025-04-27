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

# Logging configuration
def get_log_level() -> str:
    """Get the logging level"""
    return get_config('LOG_LEVEL', 'INFO')

def get_log_date_format() -> str:
    """Get the log date format"""
    return get_config('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
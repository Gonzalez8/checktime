"""
Logging configuration for CheckTime application.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from checktime.shared.config import get_log_level, get_log_date_format

# Log directory
LOG_DIR = Path('/var/log/checktime')
LOG_DIR.mkdir(exist_ok=True)

# Log files
BOT_LOG_FILE = LOG_DIR / 'bot.log'
WEB_LOG_FILE = LOG_DIR / 'web.log'
SCHEDULER_LOG_FILE = LOG_DIR / 'scheduler.log'
ERROR_LOG_FILE = LOG_DIR / 'error.log'

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = get_log_date_format()
LOG_MAX_BYTES = 1024 * 1024  # 1MB
LOG_BACKUP_COUNT = 5

# Configure root logger
logging.basicConfig(
    level=getattr(logging, get_log_level()),
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        logging.StreamHandler()
    ]
)

# Create and configure bot logger
bot_logger = logging.getLogger('checktime.bot')
bot_handler = RotatingFileHandler(
    BOT_LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT
)
bot_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
bot_logger.addHandler(bot_handler)

# Create and configure web logger
web_logger = logging.getLogger('checktime.web')
web_handler = RotatingFileHandler(
    WEB_LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT
)
web_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
web_logger.addHandler(web_handler)

# Create and configure scheduler logger
scheduler_logger = logging.getLogger('checktime.scheduler')
scheduler_handler = RotatingFileHandler(
    SCHEDULER_LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT
)
scheduler_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
scheduler_logger.addHandler(scheduler_handler)

# Create and configure error logger
error_logger = logging.getLogger('checktime.error')
error_handler = RotatingFileHandler(
    ERROR_LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT
)
error_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
error_handler.setLevel(logging.ERROR)
error_logger.addHandler(error_handler) 
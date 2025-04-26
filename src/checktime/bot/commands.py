"""
Commands for the Telegram bot.
"""

import re
import logging
from datetime import datetime
from typing import Tuple, Optional

from checktime.shared.repository import holiday_repository
from checktime.utils.telegram import TelegramClient

# Configure logging
logger = logging.getLogger(__name__)

# Command patterns
ADD_HOLIDAY_PATTERN = r'/addfestivo\s+(\d{4}-\d{2}-\d{2})(?:\s+(.+))?'
DELETE_HOLIDAY_PATTERN = r'/delfestivo\s+(\d{4}-\d{2}-\d{2})'
LIST_HOLIDAYS_COMMAND = '/listfestivos'
GET_CHAT_ID_COMMAND = '/getchatid'

def handle_get_chat_id(telegram_client: TelegramClient, chat_id: str) -> None:
    """
    Handle the /getchatid command to help users find their chat ID for configuration.
    
    Args:
        telegram_client: The Telegram client to use for sending messages
        chat_id: The chat ID of the user
    """
    message = (
        f"Your Telegram Chat ID is: `{chat_id}`\n\n"
        "Copy this ID and paste it in your CheckTime user profile to receive personalized notifications."
    )
    telegram_client.send_message(message, chat_id)
    logger.info(f"Chat ID {chat_id} sent to user")

def parse_add_holiday_command(text: str) -> Tuple[Optional[datetime.date], Optional[str]]:
    """
    Parse the /addfestivo command.
    
    Args:
        text: The command text
        
    Returns:
        Tuple containing date and description, or (None, None) if invalid
    """
    match = re.match(ADD_HOLIDAY_PATTERN, text)
    if match:
        date_str = match.group(1)
        description = match.group(2) or f"Holiday on {date_str}"
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return date, description
        except ValueError:
            return None, None
    return None, None

def parse_delete_holiday_command(text: str) -> Optional[datetime.date]:
    """
    Parse the /delfestivo command.
    
    Args:
        text: The command text
        
    Returns:
        Date object or None if invalid
    """
    match = re.match(DELETE_HOLIDAY_PATTERN, text)
    if match:
        date_str = match.group(1)
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return date
        except ValueError:
            return None
    return None

def get_help_message() -> str:
    """
    Get the help message for the bot.
    
    Returns:
        str: The help message
    """
    return (
        "Available commands:\n\n"
        "📱 */getchatid* - Get your Telegram chat ID for configuration\n\n"
        "📅 */addfestivo YYYY-MM-DD [description]* - Add a holiday\n"
        "   Example: `/addfestivo 2023-12-25 Christmas Day`\n\n"
        "🗑️ */delfestivo YYYY-MM-DD* - Delete a holiday\n"
        "   Example: `/delfestivo 2023-12-25`\n\n"
        "📋 */listfestivos* - List upcoming holidays"
    ) 
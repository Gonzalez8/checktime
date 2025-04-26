"""
Telegram bot listener for CheckTime application.
"""

import time
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any

from checktime.utils.logger import bot_logger, error_logger
from checktime.utils.telegram import TelegramClient
from checktime.shared.services.holiday_manager import HolidayManager
from checktime.shared.services.user_manager import UserManager
from checktime.shared.config import get_telegram_token
from checktime.web import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/checktime/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Telegram client
telegram_client = TelegramClient()

# Create Flask app
app = create_app()

# Command pattern for adding a holiday
ADD_HOLIDAY_PATTERN = r'/addfestivo\s+(\d{4}-\d{2}-\d{2})(?:\s+(.+))?'
# Command pattern for deleting a holiday
DELETE_HOLIDAY_PATTERN = r'/delfestivo\s+(\d{4}-\d{2}-\d{2})'
# Command for listing holidays
LIST_HOLIDAYS_COMMAND = '/listfestivos'
# Command for getting chat ID
GET_CHAT_ID_COMMAND = '/getchatid'

class TelegramBotListener:
    """Client for listening and processing Telegram commands."""
    
    def __init__(self, telegram_client: Optional[TelegramClient] = None):
        """
        Initialize the Telegram listener.
        
        Args:
            telegram_client (Optional[TelegramClient]): Telegram client
        """
        self.telegram = telegram_client or TelegramClient()
        self.user_manager = UserManager()
        self.last_update_id = None
    
    def get_user_by_chat_id(self, chat_id: str):
        """
        Get user by Telegram chat ID.
        
        Args:
            chat_id (str): Telegram chat ID
            
        Returns:
            User or None: User object if found, None otherwise
        """
        return self.user_manager.get_user_by_chat_id(chat_id)
    
    def process_command(self, message: Dict[str, Any]) -> None:
        """
        Process a received command.
        
        Args:
            message (Dict[str, Any]): Received message
        """
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "").strip()
        
        bot_logger.info(f"Command received from {chat_id}: {text}")
        
        # Process /getchatid command - this works for all users
        if text == GET_CHAT_ID_COMMAND:
            response = f"Your Telegram Chat ID is: `{chat_id}`\n\nCopy this ID and paste it in your user profile to receive notifications."
            self.telegram.send_message(response, chat_id)
            return
        
        # For commands that require authentication, find the user
        with app.app_context():
            user = self.get_user_by_chat_id(chat_id)
            if not user:
                bot_logger.warning(f"Message ignored from unauthorized chat: {chat_id}")
                self.telegram.send_message(f"You are not authorized to use this bot. Please register or update your profile at CheckTime web interface with this chat ID.", chat_id)
                return
            
            bot_logger.info(f"User {user.username} (ID: {user.id}) identified for chat ID {chat_id}")
            
            # Process /addfestivo command
            date, description = self.parse_add_holiday_command(text)
            if date and description:
                self.add_holiday(date, description, user)
                return
            
            # Process /delfestivo command
            date = self.parse_delete_holiday_command(text)
            if date:
                self.remove_holiday(date, user)
                return
            
            # Process /listfestivos command
            if text == LIST_HOLIDAYS_COMMAND:
                self.list_holidays(user)
                return
            
            # Unknown command
            if text.startswith('/'):
                self.telegram.send_message(
                    f"Hello {user.username}!\n\n"
                    "Available commands:\n"
                    "/getchatid - Get your Telegram chat ID\n"
                    "/addfestivo YYYY-MM-DD [description] - Add a holiday\n"
                    "/delfestivo YYYY-MM-DD - Delete a holiday\n"
                    "/listfestivos - List upcoming holidays", 
                    chat_id
                )
                return
    
    def parse_add_holiday_command(self, text):
        """Parse add holiday command text."""
        match = re.match(ADD_HOLIDAY_PATTERN, text)
        if match:
            date_str = match.group(1)
            description = match.group(2) or f"Holiday added by Telegram bot"
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                return date, description
            except ValueError:
                return None, None
        return None, None
    
    def parse_delete_holiday_command(self, text):
        """Parse delete holiday command text."""
        match = re.match(DELETE_HOLIDAY_PATTERN, text)
        if match:
            date_str = match.group(1)
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                return date
            except ValueError:
                return None
        return None
    
    def add_holiday(self, date: datetime.date, description: Optional[str] = None, user = None) -> None:
        """
        Add a holiday for a specific user.
        
        Args:
            date (datetime.date): Holiday date
            description (Optional[str]): Holiday description
            user: User object
        """
        try:
            date_str = date.strftime("%Y-%m-%d")
            chat_id = user.telegram_chat_id
            
            with app.app_context():
                # Create a holiday manager for this user
                holiday_manager = HolidayManager(user.id)
                
                # Add the holiday using the manager
                success = holiday_manager.add_holiday(date_str, description, user.id)
            
            if success:
                self.telegram.send_message(f"✅ Holiday added: {date_str}", chat_id)
            else:
                self.telegram.send_message(f"⚠️ Holiday {date_str} already exists.", chat_id)
            
        except Exception as e:
            error_msg = f"Error adding holiday: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}", user.telegram_chat_id if user else None)
    
    def remove_holiday(self, date: datetime.date, user = None) -> None:
        """
        Remove a holiday for a specific user.
        
        Args:
            date (datetime.date): Holiday date
            user: User object
        """
        try:
            date_str = date.strftime("%Y-%m-%d")
            chat_id = user.telegram_chat_id
            
            with app.app_context():
                # Create a holiday manager for this user
                holiday_manager = HolidayManager(user.id)
                
                # Delete the holiday using the manager
                success = holiday_manager.delete_holiday(date_str, user.id)
            
            if success:
                self.telegram.send_message(f"✅ Holiday removed: {date_str}", chat_id)
            else:
                self.telegram.send_message(f"⚠️ Holiday {date_str} does not exist.", chat_id)
            
        except Exception as e:
            error_msg = f"Error removing holiday: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}", user.telegram_chat_id if user else None)
    
    def list_holidays(self, user = None) -> None:
        """
        List upcoming holidays for a specific user.
        
        Args:
            user: User object
        """
        try:
            chat_id = user.telegram_chat_id
            
            with app.app_context():
                # Create a holiday manager for this user
                holiday_manager = HolidayManager(user.id)
                
                # Get upcoming holidays for this user
                upcoming_holidays = holiday_manager.get_upcoming_holidays(user.id)
            
            if not upcoming_holidays:
                self.telegram.send_message("📅 No upcoming holidays.", chat_id)
                return
            
            # Create the message
            message = f"📅 *Upcoming holidays for {user.username}:*\n"
            for holiday in upcoming_holidays:
                date_str = holiday.date.strftime("%Y-%m-%d")
                desc = holiday.description
                days_remaining = holiday.days_remaining
                day_text = "today" if days_remaining == 0 else f"in {days_remaining} day{'s' if days_remaining != 1 else ''}"
                message += f"- {date_str} ({desc}): {day_text}\n"
            
            self.telegram.send_message(message, chat_id)
            
        except Exception as e:
            error_msg = f"Error listing holidays: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}", user.telegram_chat_id if user else None)
    
    def listen(self) -> None:
        """Listen for and process Telegram commands."""
        bot_logger.info("Starting Telegram bot listener")
        self.telegram.send_message("🤖 Telegram bot listener started")
        
        while True:
            try:
                updates = self.telegram.get_updates(offset=self.last_update_id)
                
                for update in updates.get("result", []):
                    # Update the last processed update ID
                    update_id = update["update_id"]
                    self.last_update_id = update_id + 1
                    
                    # Process the message if it contains a command
                    if "message" in update and "text" in update["message"]:
                        self.process_command(update["message"])
                
                # Small delay to prevent high CPU usage
                time.sleep(1)
                
            except Exception as e:
                error_msg = f"Error in Telegram listener: {e}"
                error_logger.error(error_msg)
                time.sleep(60)  # Longer delay on error

def main():
    """Main function that runs the Telegram bot."""
    bot_logger.info("Starting Telegram bot")
    
    try:
        token = get_telegram_token()
        if not token:
            bot_logger.error("Telegram token not configured. Bot cannot start.")
            return
        
        listener = TelegramBotListener()
        listener.listen()
    except Exception as e:
        error_msg = f"Fatal error in Telegram bot: {e}"
        error_logger.error(error_msg)

if __name__ == "__main__":
    main() 
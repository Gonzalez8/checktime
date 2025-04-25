import time
from datetime import datetime
from typing import Optional, Dict, Any

from checktime.utils.logger import bot_logger, error_logger
from checktime.utils.telegram import TelegramClient
from checktime.shared.services.holiday_manager import HolidayManager

class TelegramBotListener:
    """Client for listening and processing Telegram commands."""
    
    def __init__(self, telegram_client: Optional[TelegramClient] = None, holiday_manager: Optional[HolidayManager] = None):
        """
        Initialize the Telegram listener.
        
        Args:
            telegram_client (Optional[TelegramClient]): Telegram client
            holiday_manager (Optional[HolidayManager]): Holiday manager
        """
        self.telegram = telegram_client or TelegramClient()
        self.holiday_manager = holiday_manager or HolidayManager()
        self.last_update_id = None
    
    def process_command(self, message: Dict[str, Any]) -> None:
        """
        Process a received command.
        
        Args:
            message (Dict[str, Any]): Received message
        """
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        
        if str(chat_id) != self.telegram.chat_id:
            bot_logger.warning(f"Message ignored from unauthorized chat: {chat_id}")
            return
        
        bot_logger.info(f"Command received: {text}")
        
        if text.startswith("/addfestivo"):
            parts = text.split(None, 2)  # Split into command, date, and description (if present)
            if len(parts) >= 2:
                date = parts[1]
                description = parts[2] if len(parts) > 2 else None
                self.add_holiday(date, description)
            else:
                self.telegram.send_message("❌ Usage: `/addfestivo YYYY-MM-DD [description]`")
        
        elif text.startswith("/delfestivo"):
            parts = text.split()
            if len(parts) == 2:
                self.remove_holiday(parts[1])
            else:
                self.telegram.send_message("❌ Usage: `/delfestivo YYYY-MM-DD`")
        
        elif text == "/listfestivos":
            self.list_holidays()
        
        else:
            bot_logger.warning(f"Command not recognized: {text}")
            self.telegram.send_message("❓ Command not recognized. Use `/addfestivo`, `/delfestivo` or `/listfestivos`.")
    
    def add_holiday(self, date: str, description: Optional[str] = None) -> None:
        """
        Add a holiday.
        
        Args:
            date (str): Date in YYYY-MM-DD format
            description (Optional[str]): Holiday description
        """
        try:
            # Validate date format
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                self.telegram.send_message("❌ Invalid format. Use: `/addfestivo YYYY-MM-DD [description]`")
                return
            
            # Use the holiday manager to save
            success = self.holiday_manager.save_holiday(date, description)
            
            if success:
                self.telegram.send_message(f"✅ Holiday added: {date}")
            else:
                self.telegram.send_message(f"⚠️ Holiday {date} already exists.")
            
        except Exception as e:
            error_msg = f"Error adding holiday: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def remove_holiday(self, date: str) -> None:
        """
        Remove a holiday.
        
        Args:
            date (str): Date in YYYY-MM-DD format
        """
        try:
            # Validate date format
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                self.telegram.send_message("❌ Invalid format. Use: `/delfestivo YYYY-MM-DD`")
                return
            
            # Use the holiday manager to delete
            success = self.holiday_manager.delete_holiday(date)
            
            if success:
                self.telegram.send_message(f"✅ Holiday removed: {date}")
            else:
                self.telegram.send_message(f"⚠️ Holiday {date} does not exist.")
            
        except Exception as e:
            error_msg = f"Error removing holiday: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
    def list_holidays(self) -> None:
        """List upcoming holidays for the year."""
        try:
            current_date = datetime.now().date()
            current_year = current_date.year
            
            # Use the holiday manager to get upcoming holidays
            upcoming_holidays = self.holiday_manager.get_upcoming_holidays()
            
            if not upcoming_holidays:
                self.telegram.send_message("📅 No upcoming holidays for this year.")
                return
            
            # Create the message
            message = f"📅 *Upcoming holidays for {current_year}:*\n"
            for date_str, desc, days_remaining in upcoming_holidays:
                day_text = "today" if days_remaining == 0 else f"in {days_remaining} day{'s' if days_remaining != 1 else ''}"
                message += f"- {date_str} ({desc}): {day_text}\n"
            
            self.telegram.send_message(message)
        except Exception as e:
            error_msg = f"Error listing holidays: {e}"
            error_logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
    
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
        listener = TelegramBotListener()
        listener.listen()
    except Exception as e:
        error_msg = f"Fatal error in Telegram bot: {e}"
        error_logger.error(error_msg)

if __name__ == "__main__":
    main() 
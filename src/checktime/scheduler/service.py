#!/usr/bin/env python
"""
Scheduler service for CheckTime application.
This script starts the scheduler service that checks schedules and performs scheduled clock-ins/outs for all users.
"""

import logging
import schedule
import time
from datetime import datetime
import threading

from checktime.scheduler.checker import CheckJCClient
from checktime.shared.config import get_log_level
from checktime.utils.telegram import TelegramClient
from checktime.shared.services.holiday_manager import HolidayManager
from checktime.shared.services.user_manager import UserManager
from checktime.shared.services.schedule_manager import ScheduleManager
from checktime.web import create_app

# Configure logging
logging.basicConfig(
    level=getattr(logging, get_log_level()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/checktime/scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Telegram client
telegram_client = TelegramClient()

# Initialize service managers
user_manager = UserManager()
schedule_manager = ScheduleManager()

# Create Flask app
app = create_app()

def is_working_day(user_id=None):
    """
    Check if today is a working day for a specific user.
    
    Args:
        user_id (int, optional): The user ID to check. If None, checks globally.
    
    Returns:
        bool: True if it's a working day, False otherwise.
    """
    with app.app_context():
        today = datetime.now().date()
        weekday = today.weekday()
        
        # Check if it's a holiday for this user using HolidayManager
        holiday_manager = HolidayManager(user_id)
        date_str = today.strftime('%Y-%m-%d')
        holidays = holiday_manager.load_holidays(user_id)
        
        if date_str in holidays:
            logger.info(f"Holiday found in database for user {user_id}: {today}")
            return False
        
        # Check if there's a schedule for today for this user using ScheduleManager
        active_period = schedule_manager.get_active_period_for_date(today, user_id)
        if not active_period:
            logger.info(f"No active period for today: {today} for user {user_id}")
            return False
        
        # Check if there's a schedule configured for this day of the week
        day_schedule = schedule_manager.get_day_schedule(active_period.id, weekday)
        if not day_schedule:
            logger.info(f"No schedule configured for today ({weekday}): {today} for user {user_id}")
            return False
        
        logger.info(f"Today is a working day: {today} for user {user_id}")
        return True

def get_schedule_times(user_id):
    """
    Get check-in and check-out times based on the current schedule in database for a specific user.
    
    Args:
        user_id (int): The user ID to get schedule for.
        
    Returns:
        tuple: (check_in_time, check_out_time) or (None, None) if no schedule.
    """
    with app.app_context():
        today = datetime.now().date()
        
        # Get schedule times for today using ScheduleManager
        check_in_time, check_out_time = schedule_manager.get_schedule_times_for_date(today, user_id)
        
        if check_in_time and check_out_time:
            logger.info(f"Using schedule from database for user {user_id}: {check_in_time} - {check_out_time}")
            return check_in_time, check_out_time
        
        # If no configuration in the database, don't clock
        logger.info(f"No schedule configured in the database for user {user_id}. Automatic clock in/out will not be performed.")
        return None, None

def perform_check_for_user(user, check_type):
    """
    Perform the check-in/out process for a specific user.
    
    Args:
        user (User): The user to perform check for.
        check_type (str): Type of check ('in' or 'out')
    """
    if not is_working_day(user.id):
        message = f"Today is not a working day or it's a holiday for user {user.username}. No check will be performed."
        logger.info(message)
        if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id:
            telegram_client.send_message(f"ℹ️ {message}", chat_id=user.telegram_chat_id)
        return

    logger.info(f"Starting {check_type} check process for user {user.username}...")
    
    try:
        with CheckJCClient(username=user.checkjc_username, password=user.checkjc_password) as client:
            client.login()
            if check_type == "in":
                client.check_in()
                icon = "🟢"
            else:
                client.check_out()
                icon = "🔴"
            logger.info(f"{check_type.capitalize()} check completed successfully for user {user.username}.")
            if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id:
                telegram_client.send_message(f"{icon} Check {check_type} completed successfully", chat_id=user.telegram_chat_id)
    except Exception as e:
        error_msg = f"Error during check {check_type} for user {user.username}: {str(e)}"
        logger.error(error_msg)
        if hasattr(user, 'telegram_chat_id') and user.telegram_chat_id:
            telegram_client.send_message(f"❌ {error_msg}", chat_id=user.telegram_chat_id)

def perform_check(check_type):
    """
    Perform the check-in/out process for all eligible users.
    
    Args:
        check_type (str): Type of check ('in' or 'out')
    """
    with app.app_context():
        # Get all users that have CheckJC configured using UserManager
        users = user_manager.get_all_with_checkjc_configured()
    
    if not users:
        logger.info(f"No users with CheckJC configured. No {check_type} checks will be performed.")
        return
        
    for user in users:
        # Create a separate thread for each user's check
        thread = threading.Thread(
            target=perform_check_for_user,
            args=(user, check_type)
        )
        thread.start()

def schedule_check():
    """Check if it's time to perform check-in/out based on schedules for all users"""
    with app.app_context():
        # Get all users with CheckJC configured using UserManager
        users = user_manager.get_all_with_checkjc_configured()
    
    if not users:
        return
        
    current_time = datetime.now().strftime("%H:%M")
    
    for user in users:
        if not is_working_day(user.id):
            continue
            
        check_in_time, check_out_time = get_schedule_times(user.id)
        
        # If no schedules defined, don't perform check
        if check_in_time is None or check_out_time is None:
            continue
            
        if current_time == check_in_time:
            # Create a separate thread for check-in
            thread = threading.Thread(
                target=perform_check_for_user,
                args=(user, "in")
            )
            thread.start()
        elif current_time == check_out_time:
            # Create a separate thread for check-out
            thread = threading.Thread(
                target=perform_check_for_user,
                args=(user, "out")
            )
            thread.start()

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
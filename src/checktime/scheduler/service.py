#!/usr/bin/env python
"""
Scheduler service for CheckTime application.
This script starts the scheduler service that checks schedules and performs scheduled clock-ins/outs.
"""

import logging
import schedule
import time
from datetime import datetime
import threading

from checktime.scheduler.checker import CheckJCClient
from checktime.shared.config import get_log_level
from checktime.utils.telegram import TelegramClient
from checktime.shared.models import SchedulePeriod, DaySchedule, Holiday
from checktime.shared.repository import holiday_repository, schedule_period_repository, day_schedule_repository

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

def is_working_day():
    """Check if today is a working day."""
    today = datetime.now().date()
    weekday = today.weekday()
    
    # Check if it's a weekend
    if weekday >= 5:  # 5 is Saturday, 6 is Sunday
        logger.info(f"Today is a weekend: {today}")
        return False
    
    # Check if it's a holiday
    holiday = holiday_repository.get_by_date(today)
    if holiday:
        logger.info(f"Holiday found in database: {today}")
        return False
    
    # Check if there's a schedule for today
    active_period = schedule_period_repository.get_active_period_for_date(today)
    if not active_period:
        logger.info(f"No active period for today: {today}")
        return False
    
    # Check if there's a schedule configured for this day of the week
    day_schedule = day_schedule_repository.get_by_period_and_day(active_period.id, weekday)
    if not day_schedule:
        logger.info(f"No schedule configured for today ({weekday}): {today}")
        return False
    
    logger.info(f"Today is a working day: {today}")
    return True

def get_schedule_times():
    """Get check-in and check-out times based on the current schedule in database"""
    today = datetime.now().date()
    weekday = today.weekday()
    
    # Get active period for today
    active_period = schedule_period_repository.get_active_period_for_date(today)
    
    if active_period:
        # Get day schedule for today's weekday
        day_schedule = day_schedule_repository.get_by_period_and_day(active_period.id, weekday)
        
        if day_schedule:
            logger.info(f"Using schedule from database: {day_schedule.check_in_time} - {day_schedule.check_out_time}")
            return day_schedule.check_in_time, day_schedule.check_out_time
    
    # If no configuration in the database, don't clock
    logger.info("No schedule configured in the database. Automatic clock in/out will not be performed.")
    return None, None

def perform_check(check_type):
    """
    Perform the check-in/out process.
    
    Args:
        check_type (str): Type of check ('in' or 'out')
    """
    if not is_working_day():
        message = "Today is not a working day or it's a holiday. No check will be performed."
        logger.info(message)
        telegram_client.send_message(f"ℹ️ {message}")
        return

    logger.info(f"Starting {check_type} check process...")
    
    try:
        with CheckJCClient() as client:
            client.login()
            if check_type == "in":
                client.check_in()
            else:
                client.check_out()
            logger.info(f"{check_type.capitalize()} check completed successfully.")
    except Exception as e:
        error_msg = f"Error during {check_type} check: {str(e)}"
        logger.error(error_msg)
        telegram_client.send_message(f"❌ {error_msg}")

def perform_check_in():
    """Perform the check-in process."""
    perform_check("in")

def perform_check_out():
    """Perform the check-out process."""
    perform_check("out")

def schedule_check():
    """Check if it's time to perform check-in/out based on the schedule"""
    if not is_working_day():
        return

    check_in_time, check_out_time = get_schedule_times()
    
    # If no schedules defined, don't perform check
    if check_in_time is None or check_out_time is None:
        return
        
    current_time = datetime.now().strftime("%H:%M")
    
    if current_time == check_in_time:
        perform_check_in()
    elif current_time == check_out_time:
        perform_check_out()

def main():
    """Main function that runs only the scheduler service."""
    logger.info("Starting automatic check-in/out service...")
    telegram_client.send_message("🚀 Starting automatic check-in/out service")

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
            telegram_client.send_message(f"❌ {error_msg}")
            time.sleep(300)  # Wait 5 minutes before retrying

if __name__ == "__main__":
    main() 
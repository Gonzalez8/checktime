"""
Holiday management service for CheckTime application.
"""

import logging
from datetime import datetime
from typing import Set, Optional, List, Tuple

from checktime.shared.repository.holiday_repository import HolidayRepository

# Create logger
logger = logging.getLogger(__name__)

class HolidayManager:
    """Manager for holidays in the system."""
    
    def __init__(self):
        """Initialize the holiday manager."""
        self.repository = HolidayRepository()
    
    def load_holidays(self) -> Set[str]:
        """
        Load holidays from the database.
        
        Returns:
            Set[str]: Set of holiday dates in YYYY-MM-DD format
        """
        try:
            holidays = set(self.repository.get_all_dates())
            logger.info(f"Loaded {len(holidays)} holidays from database")
            return holidays
        except Exception as e:
            error_msg = f"Error loading holidays: {e}"
            logger.error(error_msg)
            return set()
    
    def add_holiday(self, date: str, description: Optional[str] = None) -> bool:
        """
        Add a holiday to the database.
        
        Args:
            date (str): Date in YYYY-MM-DD format
            description (Optional[str]): Description of the holiday
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert string date to datetime.date
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            
            # Check if the holiday already exists
            existing = self.repository.get_by_date(date_obj)
            if existing:
                logger.info(f"Holiday {date} already exists")
                return False
            
            # Set default description if not provided
            if not description:
                description = f"Added via API on {datetime.now()}"
            
            # Create the holiday
            self.repository.create(date_obj, description)
            logger.info(f"Holiday {date} saved")
            return True
            
        except Exception as e:
            error_msg = f"Error saving holiday: {e}"
            logger.error(error_msg)
            return False
    
    def delete_holiday(self, date: str) -> bool:
        """
        Delete a holiday from the database.
        
        Args:
            date (str): Date in YYYY-MM-DD format
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert string date to datetime.date
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            
            # Check if the holiday exists
            holiday = self.repository.get_by_date(date_obj)
            if not holiday:
                logger.info(f"Holiday {date} does not exist")
                return False
            
            # Delete the holiday
            self.repository.delete(holiday)
            logger.info(f"Holiday {date} deleted")
            return True
            
        except Exception as e:
            error_msg = f"Error deleting holiday: {e}"
            logger.error(error_msg)
            return False
    
    def get_upcoming_holidays(self) -> List[Tuple[str, str, int]]:
        """
        Get upcoming holidays for the current year.
        
        Returns:
            List[Tuple[str, str, int]]: List of (date_str, description, days_remaining) tuples
        """
        try:
            current_date = datetime.now().date()
            current_year = current_date.year
            
            # Get all holidays
            holidays = self.repository.get_all()
            
            # Filter to show only upcoming holidays
            upcoming = []
            for holiday in holidays:
                holiday_date = holiday.date
                if holiday_date >= current_date and holiday_date.year == current_year:
                    days_remaining = (holiday_date - current_date).days
                    upcoming.append((holiday.date_str, holiday.description, days_remaining))
            
            return sorted(upcoming, key=lambda x: x[0])
            
        except Exception as e:
            error_msg = f"Error getting upcoming holidays: {e}"
            logger.error(error_msg)
            return []
    
    # Alias para mantener compatibilidad con el código existente
    save_holiday = add_holiday
    
    def clear_holidays(self) -> bool:
        """
        Clear all holidays from in-memory cache (for testing/resetting).
        This doesn't delete from database, just forces a reload.
        
        Returns:
            bool: True
        """
        logger.info("Holiday cache cleared")
        return True 
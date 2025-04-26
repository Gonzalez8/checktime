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
    
    def __init__(self, user_id: Optional[int] = None):
        """
        Initialize the holiday manager.
        
        Args:
            user_id (Optional[int]): Optional user ID to associate with this manager
        """
        self.repository = HolidayRepository()
        self.user_id = user_id
    
    def load_holidays(self, user_id: Optional[int] = None) -> Set[str]:
        """
        Load holidays from the database.
        
        Args:
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            Set[str]: Set of holiday dates in YYYY-MM-DD format
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for load_holidays")
                return set()
                
            holidays = set(self.repository.get_all_dates(user_id))
            logger.info(f"Loaded {len(holidays)} holidays from database for user {user_id}")
            return holidays
        except Exception as e:
            error_msg = f"Error loading holidays: {e}"
            logger.error(error_msg)
            return set()
    
    def add_holiday(self, date: str, description: Optional[str] = None, user_id: Optional[int] = None) -> bool:
        """
        Add a holiday to the database.
        
        Args:
            date (str): Date in YYYY-MM-DD format
            description (Optional[str]): Description of the holiday
            user_id (Optional[int]): User ID to associate with the holiday
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for add_holiday")
                return False
                
            # Convert string date to datetime.date
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            
            # Check if the holiday already exists for this user
            existing = self.repository.get_by_date(date_obj, user_id)
            if existing:
                logger.info(f"Holiday {date} already exists for user {user_id}")
                return False
            
            # Set default description if not provided
            if not description:
                description = f"Added via API on {datetime.now()}"
            
            # Create the holiday
            self.repository.create(date_obj, description, user_id)
            logger.info(f"Holiday {date} saved for user {user_id}")
            return True
            
        except Exception as e:
            error_msg = f"Error saving holiday: {e}"
            logger.error(error_msg)
            return False
    
    def delete_holiday(self, date: str, user_id: Optional[int] = None) -> bool:
        """
        Delete a holiday from the database.
        
        Args:
            date (str): Date in YYYY-MM-DD format
            user_id (Optional[int]): User ID to filter holidays
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for delete_holiday")
                return False
                
            # Convert string date to datetime.date
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            
            # Check if the holiday exists for this user
            holiday = self.repository.get_by_date(date_obj, user_id)
            if not holiday:
                logger.info(f"Holiday {date} does not exist for user {user_id}")
                return False
            
            # Delete the holiday
            self.repository.delete(holiday)
            logger.info(f"Holiday {date} deleted for user {user_id}")
            return True
            
        except Exception as e:
            error_msg = f"Error deleting holiday: {e}"
            logger.error(error_msg)
            return False
    
    def get_upcoming_holidays(self, user_id: Optional[int] = None) -> List[Tuple[str, str, int]]:
        """
        Get upcoming holidays for the current year.
        
        Args:
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            List[Tuple[str, str, int]]: List of (date_str, description, days_remaining) tuples
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_upcoming_holidays")
                return []
                
            current_date = datetime.now().date()
            current_year = current_date.year
            
            # Get holidays for the specified user
            holidays = self.repository.get_all(user_id)
            
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
    
    
    def clear_holidays(self) -> bool:
        """
        Clear all holidays from in-memory cache (for testing/resetting).
        This doesn't delete from database, just forces a reload.
        
        Returns:
            bool: True
        """
        logger.info("Holiday cache cleared")
        return True 
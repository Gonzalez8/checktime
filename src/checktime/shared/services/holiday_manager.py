"""
Holiday management service for CheckTime application.
"""

import logging
from datetime import datetime, timedelta
from typing import Set, Optional, List, Tuple, Dict, Any

from checktime.shared.repository.holiday_repository import HolidayRepository
from checktime.shared.models.holiday import Holiday

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
    
    def get_upcoming_holidays(self, user_id: Optional[int] = None) -> List[Holiday]:
        """
        Get upcoming holidays for the current year.
        
        Args:
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            List[Holiday]: List of upcoming Holiday objects
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
                if holiday.date >= current_date and holiday.date.year == current_year:
                    # Calculate days_remaining and add it as an attribute to the holiday object
                    days_remaining = (holiday.date - current_date).days
                    holiday.days_remaining = days_remaining
                    upcoming.append(holiday)
            
            return sorted(upcoming, key=lambda x: x.date)
            
        except Exception as e:
            error_msg = f"Error getting upcoming holidays: {e}"
            logger.error(error_msg)
            return []
    
    def get_holidays_for_date_range(self, start_date: datetime.date, end_date: datetime.date, user_id: Optional[int] = None) -> List[Holiday]:
        """
        Get all holidays within a date range for a specific user.
        
        Args:
            start_date (datetime.date): Start date
            end_date (datetime.date): End date
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            List[Holiday]: List of holidays within the date range
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_holidays_for_date_range")
                return []
                
            holidays = self.repository.get_holidays_for_date_range(start_date, end_date, user_id)
            logger.info(f"Found {len(holidays)} holidays for date range {start_date} to {end_date}, user {user_id}")
            return holidays
        except Exception as e:
            error_msg = f"Error getting holidays for date range: {e}"
            logger.error(error_msg)
            return []
    
    def get_all_holidays(self, user_id: Optional[int] = None) -> List[Holiday]:
        """
        Get all holidays for a user.
        
        Args:
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            List[Holiday]: List of all holidays for the user
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_all_holidays")
                return []
                
            holidays = self.repository.get_all(user_id)
            logger.info(f"Found {len(holidays)} holidays for user {user_id}")
            return holidays
        except Exception as e:
            error_msg = f"Error getting all holidays: {e}"
            logger.error(error_msg)
            return []
    
    def get_holiday_by_id(self, holiday_id: int, user_id: Optional[int] = None) -> Optional[Holiday]:
        """
        Get a holiday by ID.
        
        Args:
            holiday_id (int): ID of the holiday to retrieve
            user_id (Optional[int]): User ID to filter
            
        Returns:
            Optional[Holiday]: Holiday if found, None otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_holiday_by_id")
                return None
                
            holiday = self.repository.get_by_id(holiday_id, user_id)
            if holiday:
                logger.info(f"Found holiday with ID {holiday_id} for user {user_id}")
            else:
                logger.info(f"No holiday found with ID {holiday_id} for user {user_id}")
            return holiday
        except Exception as e:
            error_msg = f"Error getting holiday by ID: {e}"
            logger.error(error_msg)
            return None
    
    def update_holiday(self, holiday_id: int, date: datetime.date, description: str, user_id: Optional[int] = None) -> bool:
        """
        Update a holiday.
        
        Args:
            holiday_id (int): ID of the holiday to update
            date (datetime.date): New date for the holiday
            description (str): New description for the holiday
            user_id (Optional[int]): User ID to filter
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for update_holiday")
                return False
                
            # Get the holiday to update
            holiday = self.repository.get_by_id(holiday_id, user_id)
            if not holiday:
                logger.warning(f"No holiday found with ID {holiday_id} for user {user_id}")
                return False
            
            # Check if the new date would conflict with an existing holiday
            existing = self.repository.get_by_date(date, user_id)
            if existing and existing.id != holiday_id:
                logger.warning(f"Holiday already exists for date {date} and user {user_id}")
                return False
            
            # Update the holiday
            updated_holiday = self.repository.update(holiday, date, description)
            logger.info(f"Updated holiday with ID {holiday_id} for user {user_id}")
            return True
        except Exception as e:
            error_msg = f"Error updating holiday: {e}"
            logger.error(error_msg)
            return False
    
    def delete_holiday_by_id(self, holiday_id: int, user_id: Optional[int] = None) -> bool:
        """
        Delete a holiday by ID.
        
        Args:
            holiday_id (int): ID of the holiday to delete
            user_id (Optional[int]): User ID to filter
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for delete_holiday_by_id")
                return False
                
            # Get the holiday to delete
            holiday = self.repository.get_by_id(holiday_id, user_id)
            if not holiday:
                logger.warning(f"No holiday found with ID {holiday_id} for user {user_id}")
                return False
            
            # Delete the holiday
            self.repository.delete(holiday)
            logger.info(f"Deleted holiday with ID {holiday_id} for user {user_id}")
            return True
        except Exception as e:
            error_msg = f"Error deleting holiday by ID: {e}"
            logger.error(error_msg)
            return False
    
    def reload_holidays(self, user_id: Optional[int] = None) -> bool:
        """
        Reload holidays from the database.
        
        Args:
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for reload_holidays")
                return False
                
            # Clear existing holidays
            self.clear_holidays()
            
            # Load holidays from database
            self.load_holidays(user_id)
            
            logger.info(f"Reloaded holidays for user {user_id}")
            return True
        except Exception as e:
            error_msg = f"Error reloading holidays: {e}"
            logger.error(error_msg)
            return False
    
    def add_holiday_range(self, start_date: datetime.date, end_date: datetime.date, 
                         description: str, skip_weekends: bool = True, 
                         user_id: Optional[int] = None) -> Dict[str, int]:
        """
        Add a range of holidays.
        
        Args:
            start_date (datetime.date): Start date
            end_date (datetime.date): End date
            description (str): Description for the holidays
            skip_weekends (bool): Whether to skip weekends
            user_id (Optional[int]): User ID to associate with the holidays
            
        Returns:
            Dict[str, int]: Dictionary with added, weekends_skipped, and existing_skipped counts
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for add_holiday_range")
                return {"added": 0, "weekends_skipped": 0, "existing_skipped": 0}
                
            # Get existing holidays to avoid duplicates
            all_holidays = self.repository.get_all(user_id)
            existing_holidays = set(h.date for h in all_holidays)
            
            # Initialize counters
            days_added = 0
            weekends_skipped = 0
            existing_skipped = 0
            
            # Calculate the date range
            current_date = start_date
            while current_date <= end_date:
                # Skip weekends if requested
                if skip_weekends and current_date.isoweekday() in [6, 7]:  # Saturday and Sunday
                    weekends_skipped += 1
                    current_date += timedelta(days=1)
                    continue
                    
                # Skip existing holidays
                if current_date in existing_holidays:
                    existing_skipped += 1
                    current_date += timedelta(days=1)
                    continue
                    
                # Add new holiday
                self.repository.create(current_date, description, user_id)
                days_added += 1
                current_date += timedelta(days=1)
            
            logger.info(f"Added {days_added} holidays for date range {start_date} to {end_date}, user {user_id}")
            return {
                "added": days_added,
                "weekends_skipped": weekends_skipped,
                "existing_skipped": existing_skipped
            }
        except Exception as e:
            error_msg = f"Error adding holiday range: {e}"
            logger.error(error_msg)
            return {"added": 0, "weekends_skipped": 0, "existing_skipped": 0}
    
    def import_ics_file(self, file_path: str, user_id: Optional[int] = None) -> Dict[str, int]:
        """
        Import holidays from an ICS file.
        
        Args:
            file_path (str): Path to the ICS file
            user_id (Optional[int]): User ID to associate with the holidays
            
        Returns:
            Dict[str, int]: Dictionary with added and skipped counts
        """
        try:
            # Check if icalendar is available
            try:
                from icalendar import Calendar
            except ImportError:
                logger.error("icalendar library not available")
                return {"added": 0, "skipped": 0}
                
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for import_ics_file")
                return {"added": 0, "skipped": 0}
                
            # Parse the ICS file
            with open(file_path, 'rb') as f:
                cal = Calendar.from_ical(f.read())
            
            # Process events
            events_added = 0
            duplicates = 0
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    event_date = component.get('dtstart').dt
                    
                    # If event_date is a datetime (not just a date), convert to date
                    if isinstance(event_date, datetime):
                        event_date = event_date.date()
                    
                    # Get event summary/description
                    summary = component.get('summary', 'Imported Holiday')
                    
                    # Check if holiday already exists
                    existing = self.repository.get_by_date(event_date, user_id)
                    if existing:
                        duplicates += 1
                        continue
                    
                    # Add to database
                    self.repository.create(event_date, str(summary), user_id)
                    events_added += 1
            
            logger.info(f"Imported {events_added} holidays from ICS file for user {user_id}")
            return {"added": events_added, "skipped": duplicates}
        except Exception as e:
            error_msg = f"Error importing ICS file: {e}"
            logger.error(error_msg)
            return {"added": 0, "skipped": 0}
    
    def import_ics_data(self, file_data: bytes, user_id: Optional[int] = None) -> Dict[str, int]:
        """
        Import holidays from ICS data.
        
        Args:
            file_data (bytes): ICS file data
            user_id (Optional[int]): User ID to associate with the holidays
            
        Returns:
            Dict[str, int]: Dictionary with added and skipped counts
        """
        try:
            # Check if icalendar is available
            try:
                from icalendar import Calendar
            except ImportError:
                logger.error("icalendar library not available")
                return {"added": 0, "skipped": 0}
                
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for import_ics_data")
                return {"added": 0, "skipped": 0}
                
            # Parse the ICS data
            cal = Calendar.from_ical(file_data)
            
            # Process events
            events_added = 0
            duplicates = 0
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    event_date = component.get('dtstart').dt
                    
                    # Skip if not a date (e.g. datetime)
                    if not isinstance(event_date, datetime.date):
                        # If event_date is a datetime, convert to date
                        if isinstance(event_date, datetime):
                            event_date = event_date.date()
                        else:
                            continue
                    
                    summary = str(component.get('summary', 'Imported Holiday'))
                    
                    # Check if holiday already exists
                    existing = self.repository.get_by_date(event_date, user_id)
                    if existing:
                        duplicates += 1
                        continue
                    
                    # Create new holiday
                    self.repository.create(event_date, summary, user_id)
                    events_added += 1
            
            logger.info(f"Imported {events_added} holidays from ICS data for user {user_id}")
            return {"added": events_added, "skipped": duplicates}
        except Exception as e:
            error_msg = f"Error importing ICS data: {e}"
            logger.error(error_msg)
            return {"added": 0, "skipped": 0}
    
    def get_all_dates(self, user_id: Optional[int] = None) -> List[str]:
        """
        Get all holiday dates as strings (YYYY-MM-DD).
        
        Args:
            user_id (Optional[int]): User ID to filter holidays
            
        Returns:
            List[str]: List of holiday dates as strings
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_all_dates")
                return []
                
            dates = self.repository.get_all_dates(user_id)
            logger.info(f"Found {len(dates)} holiday dates for user {user_id}")
            return dates
        except Exception as e:
            error_msg = f"Error getting all dates: {e}"
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
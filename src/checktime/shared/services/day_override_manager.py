"""
DayOverride management service for CheckTime application.
"""

import logging
from datetime import date
from typing import List, Optional, Tuple

from checktime.shared.repository.day_override_repository import DayOverrideRepository
from checktime.shared.models.schedule import DayOverride

# Create logger
logger = logging.getLogger(__name__)

class DayOverrideManager:
    """Manager for day overrides in the system."""
    
    def __init__(self, user_id: Optional[int] = None):
        """
        Initialize the day override manager.
        
        Args:
            user_id (Optional[int]): Optional user ID to associate with this manager
        """
        self.repository = DayOverrideRepository()
        self.user_id = user_id
    
    def get_override_for_date(self, target_date: date, user_id: Optional[int] = None) -> Optional[DayOverride]:
        """
        Get a day override for a specific date.
        
        Args:
            target_date (date): The date to check
            user_id (Optional[int]): User ID to filter
            
        Returns:
            Optional[DayOverride]: Day override if found, None otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_override_for_date")
                return None
                
            override = self.repository.get_by_user_and_date(user_id, target_date)
            if override:
                logger.info(f"Found override for date {target_date} and user {user_id}")
            else:
                logger.info(f"No override found for date {target_date} and user {user_id}")
            return override
        except Exception as e:
            error_msg = f"Error getting override for date: {e}"
            logger.error(error_msg)
            return None
    
    def get_overrides_in_range(self, start_date: date, end_date: date, user_id: Optional[int] = None) -> List[DayOverride]:
        """
        Get all overrides within a date range.
        
        Args:
            start_date (date): Start date
            end_date (date): End date
            user_id (Optional[int]): User ID to filter
            
        Returns:
            List[DayOverride]: List of day overrides in the range
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_overrides_in_range")
                return []
                
            overrides = self.repository.get_by_user_in_date_range(user_id, start_date, end_date)
            logger.info(f"Found {len(overrides)} overrides for date range {start_date} to {end_date}, user {user_id}")
            return overrides
        except Exception as e:
            error_msg = f"Error getting overrides in range: {e}"
            logger.error(error_msg)
            return []
    
    def create_override(self, target_date: date, check_in_time: str, check_out_time: str, 
                       description: Optional[str] = None, user_id: Optional[int] = None) -> Optional[DayOverride]:
        """
        Create a new day override.
        
        Args:
            target_date (date): The date for the override
            check_in_time (str): Check-in time (format: "09:00")
            check_out_time (str): Check-out time (format: "18:00")
            description (Optional[str]): Optional description for the override
            user_id (Optional[int]): User ID to associate with the override
            
        Returns:
            Optional[DayOverride]: Created day override, or None on error
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for create_override")
                return None
                
            # Check if override already exists
            existing = self.repository.get_by_user_and_date(user_id, target_date)
            if existing:
                logger.warning(f"Override already exists for date {target_date} and user {user_id}")
                return None
                
            # Create new override
            override = DayOverride(
                date=target_date,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                description=description,
                user_id=user_id
            )
            created = self.repository.create(override)
            logger.info(f"Created override for date {target_date} and user {user_id}")
            return created
        except Exception as e:
            error_msg = f"Error creating override: {e}"
            logger.error(error_msg)
            return None
    
    def update_override(self, target_date: date, check_in_time: Optional[str] = None,
                       check_out_time: Optional[str] = None, description: Optional[str] = None,
                       user_id: Optional[int] = None) -> Optional[DayOverride]:
        """
        Update an existing day override.
        
        Args:
            target_date (date): The date of the override to update
            check_in_time (Optional[str]): New check-in time (format: "09:00")
            check_out_time (Optional[str]): New check-out time (format: "18:00")
            description (Optional[str]): New description
            user_id (Optional[int]): User ID to filter
            
        Returns:
            Optional[DayOverride]: Updated day override, or None on error
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for update_override")
                return None
                
            # Get existing override
            override = self.repository.get_by_user_and_date(user_id, target_date)
            if not override:
                logger.warning(f"No override found for date {target_date} and user {user_id}")
                return None
                
            # Update fields if provided
            if check_in_time is not None:
                override.check_in_time = check_in_time
            if check_out_time is not None:
                override.check_out_time = check_out_time
            if description is not None:
                override.description = description
                
            # Save changes
            updated = self.repository.update(override)
            logger.info(f"Updated override for date {target_date} and user {user_id}")
            return updated
        except Exception as e:
            error_msg = f"Error updating override: {e}"
            logger.error(error_msg)
            return None
    
    def delete_override(self, target_date: date, user_id: Optional[int] = None) -> bool:
        """
        Delete a day override.
        
        Args:
            target_date (date): The date of the override to delete
            user_id (Optional[int]): User ID to filter
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for delete_override")
                return False
                
            # Delete the override
            deleted = self.repository.delete_by_user_and_date(user_id, target_date)
            if deleted:
                logger.info(f"Deleted override for date {target_date} and user {user_id}")
            else:
                logger.info(f"No override found to delete for date {target_date} and user {user_id}")
            return deleted
        except Exception as e:
            error_msg = f"Error deleting override: {e}"
            logger.error(error_msg)
            return False 
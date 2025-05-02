"""
Schedule management service for CheckTime application.
"""

import logging
from datetime import date
from typing import List, Optional, Tuple, Dict, Any

from checktime.shared.repository.schedule_repository import SchedulePeriodRepository, DayScheduleRepository
from checktime.shared.repository.day_override_repository import DayOverrideRepository
from checktime.shared.models.schedule import SchedulePeriod, DaySchedule

# Create logger
logger = logging.getLogger(__name__)

class ScheduleManager:
    """Manager for schedules in the system."""
    
    def __init__(self, user_id: Optional[int] = None):
        """
        Initialize the schedule manager.
        
        Args:
            user_id (Optional[int]): Optional user ID to associate with this manager
        """
        self.period_repository = SchedulePeriodRepository()
        self.day_repository = DayScheduleRepository()
        self.user_id = user_id
    
    # Schedule Period methods
    def get_all_periods(self, user_id: Optional[int] = None) -> List[SchedulePeriod]:
        """
        Get all schedule periods for a user.
        
        Args:
            user_id (Optional[int]): User ID to filter periods
            
        Returns:
            List[SchedulePeriod]: List of schedule periods
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_all_periods")
                return []
                
            periods = self.period_repository.get_all(user_id)
            logger.info(f"Found {len(periods)} schedule periods for user {user_id}")
            return periods
        except Exception as e:
            error_msg = f"Error getting schedule periods: {e}"
            logger.error(error_msg)
            return []
    
    def get_period_by_id(self, period_id: int, user_id: Optional[int] = None) -> Optional[SchedulePeriod]:
        """
        Get a schedule period by ID.
        
        Args:
            period_id (int): Period ID to fetch
            user_id (Optional[int]): User ID to filter
            
        Returns:
            Optional[SchedulePeriod]: Schedule period if found, None otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            
            period = self.period_repository.get_by_id(period_id, user_id)
            if period:
                logger.info(f"Found period {period.name} for user {user_id}")
            else:
                logger.info(f"No period found with ID {period_id} for user {user_id}")
            return period
        except Exception as e:
            error_msg = f"Error getting period by ID: {e}"
            logger.error(error_msg)
            return None
    
    def get_active_periods(self, user_id: Optional[int] = None) -> List[SchedulePeriod]:
        """
        Get all active schedule periods for a user.
        
        Args:
            user_id (Optional[int]): User ID to filter periods
            
        Returns:
            List[SchedulePeriod]: List of active schedule periods
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_active_periods")
                return []
                
            periods = self.period_repository.get_active_periods(user_id)
            logger.info(f"Found {len(periods)} active schedule periods for user {user_id}")
            return periods
        except Exception as e:
            error_msg = f"Error getting active periods: {e}"
            logger.error(error_msg)
            return []
    
    def get_active_period_for_date(self, target_date: date, user_id: Optional[int] = None) -> Optional[SchedulePeriod]:
        """
        Get the active schedule period for a specific date.
        
        Args:
            target_date (date): The date to check
            user_id (Optional[int]): User ID to filter periods
            
        Returns:
            Optional[SchedulePeriod]: Active schedule period for the date, or None if not found
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_active_period_for_date")
                return None
                
            period = self.period_repository.get_active_period_for_date(target_date, user_id)
            if period:
                logger.info(f"Found active period {period.name} for date {target_date} and user {user_id}")
            else:
                logger.info(f"No active period found for date {target_date} and user {user_id}")
            return period
        except Exception as e:
            error_msg = f"Error getting active period for date: {e}"
            logger.error(error_msg)
            return None
    
    def get_periods_for_date_range(self, start_date: date, end_date: date, user_id: Optional[int] = None) -> List[SchedulePeriod]:
        """
        Get all schedule periods that overlap with a date range for a specific user.
        
        Args:
            start_date (date): Start date
            end_date (date): End date
            user_id (Optional[int]): User ID to filter periods
            
        Returns:
            List[SchedulePeriod]: List of schedule periods that overlap with the date range
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_periods_for_date_range")
                return []
                
            periods = self.period_repository.get_periods_for_date_range(start_date, end_date, user_id)
            logger.info(f"Found {len(periods)} schedule periods for date range {start_date} to {end_date}, user {user_id}")
            return periods
        except Exception as e:
            error_msg = f"Error getting periods for date range: {e}"
            logger.error(error_msg)
            return []
    
    def get_active_periods_after_date(self, target_date: date, user_id: Optional[int] = None) -> List[SchedulePeriod]:
        """
        Get all active schedule periods that start after or include a specific date.
        
        Args:
            target_date (date): The date to check
            user_id (Optional[int]): User ID to filter periods
            
        Returns:
            List[SchedulePeriod]: List of active schedule periods after the date
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_active_periods_after_date")
                return []
                
            periods = self.period_repository.get_active_periods_after_date(target_date, user_id)
            logger.info(f"Found {len(periods)} active schedule periods after date {target_date}, user {user_id}")
            return periods
        except Exception as e:
            error_msg = f"Error getting active periods after date: {e}"
            logger.error(error_msg)
            return []
    
    def create_period(self, name: str, start_date: date, end_date: date, 
                     user_id: Optional[int] = None, is_active: bool = True) -> Optional[SchedulePeriod]:
        """
        Create a new schedule period.
        
        Args:
            name (str): Name of the period
            start_date (date): Start date
            end_date (date): End date
            user_id (Optional[int]): User ID to associate with the period
            is_active (bool): Whether the period is active
            
        Returns:
            Optional[SchedulePeriod]: Created schedule period, or None on error
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for create_period")
                return None
                
            # Check for overlap with existing periods
            if self.period_repository.check_overlap(start_date, end_date, user_id):
                logger.warning(f"Period overlap detected for user {user_id}: {start_date} to {end_date}")
                return None
                
            period = self.period_repository.create_period(name, start_date, end_date, user_id, is_active)
            logger.info(f"Created period {period.name} for user {user_id}")
            return period
        except Exception as e:
            error_msg = f"Error creating period: {e}"
            logger.error(error_msg)
            return None
    
    def update_period(self, period_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Optional[SchedulePeriod]:
        """
        Update a schedule period.
        
        Args:
            period_id (int): ID of the period to update
            data (Dict[str, Any]): Data to update (name, start_date, end_date, is_active)
            user_id (Optional[int]): User ID to filter
            
        Returns:
            Optional[SchedulePeriod]: Updated schedule period, or None on error
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            
            # Get the period
            period = self.period_repository.get_by_id(period_id, user_id)
            if not period:
                logger.warning(f"Period with ID {period_id} not found for user {user_id}")
                return None
                
            # Check for overlap with existing periods if dates are changing
            if ('start_date' in data or 'end_date' in data) and self.period_repository.check_overlap(
                data.get('start_date', period.start_date),
                data.get('end_date', period.end_date),
                user_id,
                exclude_id=period_id
            ):
                logger.warning(f"Period overlap detected for user {user_id}")
                return None
                
            # Update the period
            updated_period = self.period_repository.update_period(
                period,
                name=data.get('name'),
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                is_active=data.get('is_active')
            )
            
            logger.info(f"Updated period {updated_period.name} for user {user_id}")
            return updated_period
        except Exception as e:
            error_msg = f"Error updating period: {e}"
            logger.error(error_msg)
            return None
    
    def delete_period(self, period_id: int, user_id: Optional[int] = None) -> bool:
        """
        Delete a schedule period.
        
        Args:
            period_id (int): ID of the period to delete
            user_id (Optional[int]): User ID to filter
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            
            # Get the period
            period = self.period_repository.get_by_id(period_id, user_id)
            if not period:
                logger.warning(f"Period with ID {period_id} not found for user {user_id}")
                return False
                
            # Delete the period
            self.period_repository.delete(period)
            logger.info(f"Deleted period {period.name} for user {user_id}")
            return True
        except Exception as e:
            error_msg = f"Error deleting period: {e}"
            logger.error(error_msg)
            return False
    
    # Day Schedule methods
    def get_day_schedule(self, period_id: int, day_of_week: int) -> Optional[DaySchedule]:
        """
        Get a day schedule by period ID and day of week.
        
        Args:
            period_id (int): Period ID
            day_of_week (int): Day of week (0-6, Monday-Sunday)
            
        Returns:
            Optional[DaySchedule]: Day schedule if found, None otherwise
        """
        try:
            day_schedule = self.day_repository.get_by_period_and_day(period_id, day_of_week)
            if day_schedule:
                logger.info(f"Found day schedule for period {period_id}, day {day_of_week}")
            else:
                logger.info(f"No day schedule found for period {period_id}, day {day_of_week}")
            return day_schedule
        except Exception as e:
            error_msg = f"Error getting day schedule: {e}"
            logger.error(error_msg)
            return None
    
    def get_day_schedule_by_id(self, day_schedule_id: int) -> Optional[DaySchedule]:
        """
        Get a day schedule by ID.
        
        Args:
            day_schedule_id (int): ID of the day schedule to retrieve
            
        Returns:
            Optional[DaySchedule]: Day schedule if found, None otherwise
        """
        try:
            day_schedule = self.day_repository.get_by_id(day_schedule_id)
            if day_schedule:
                logger.info(f"Found day schedule with ID {day_schedule_id}")
            else:
                logger.info(f"No day schedule found with ID {day_schedule_id}")
            return day_schedule
        except Exception as e:
            error_msg = f"Error getting day schedule by ID: {e}"
            logger.error(error_msg)
            return None
    
    def get_all_day_schedules(self, period_id: int) -> List[DaySchedule]:
        """
        Get all day schedules for a period.
        
        Args:
            period_id (int): Period ID
            
        Returns:
            List[DaySchedule]: List of day schedules
        """
        try:
            day_schedules = self.day_repository.get_all_by_period(period_id)
            logger.info(f"Found {len(day_schedules)} day schedules for period {period_id}")
            return day_schedules
        except Exception as e:
            error_msg = f"Error getting day schedules: {e}"
            logger.error(error_msg)
            return []
    
    def create_day_schedule(self, period_id: int, day_of_week: int, 
                          check_in_time: str, check_out_time: str) -> Optional[DaySchedule]:
        """
        Create a new day schedule.
        
        Args:
            period_id (int): Period ID
            day_of_week (int): Day of week (0-6, Monday-Sunday)
            check_in_time (str): Check-in time (format: "09:00")
            check_out_time (str): Check-out time (format: "18:00")
            
        Returns:
            Optional[DaySchedule]: Created day schedule, or None on error
        """
        try:
            # Check if a day schedule already exists for this period and day
            existing = self.day_repository.get_by_period_and_day(period_id, day_of_week)
            if existing:
                logger.warning(f"Day schedule already exists for period {period_id}, day {day_of_week}")
                return None
                
            day_schedule = self.day_repository.create_day_schedule(
                period_id, day_of_week, check_in_time, check_out_time
            )
            logger.info(f"Created day schedule for period {period_id}, day {day_of_week}")
            return day_schedule
        except Exception as e:
            error_msg = f"Error creating day schedule: {e}"
            logger.error(error_msg)
            return None
    
    def update_day_schedule(self, day_schedule_id: int, check_in_time: Optional[str] = None, 
                          check_out_time: Optional[str] = None) -> Optional[DaySchedule]:
        """
        Update a day schedule.
        
        Args:
            day_schedule_id (int): ID of the day schedule to update
            check_in_time (Optional[str]): New check-in time (format: "09:00")
            check_out_time (Optional[str]): New check-out time (format: "18:00")
            
        Returns:
            Optional[DaySchedule]: Updated day schedule, or None on error
        """
        try:
            # Get the day schedule
            day_schedule = self.day_repository.get_by_id(day_schedule_id)
            if not day_schedule:
                logger.warning(f"Day schedule with ID {day_schedule_id} not found")
                return None
                
            # Update the day schedule
            updated = self.day_repository.update_day_schedule(
                day_schedule,
                check_in_time=check_in_time,
                check_out_time=check_out_time
            )
            logger.info(f"Updated day schedule with ID {day_schedule_id}")
            return updated
        except Exception as e:
            error_msg = f"Error updating day schedule: {e}"
            logger.error(error_msg)
            return None
    
    def create_or_update_day_schedule(self, period_id: int, day_of_week: int, 
                                    check_in_time: str, check_out_time: str) -> Optional[DaySchedule]:
        """
        Create or update a day schedule.
        
        Args:
            period_id (int): Period ID
            day_of_week (int): Day of week (0-6, Monday-Sunday)
            check_in_time (str): Check-in time (format: "09:00")
            check_out_time (str): Check-out time (format: "18:00")
            
        Returns:
            Optional[DaySchedule]: Created or updated day schedule, or None on error
        """
        try:
            # Check if a day schedule already exists for this period and day
            existing = self.day_repository.get_by_period_and_day(period_id, day_of_week)
            
            if existing:
                # Update existing day schedule
                updated = self.day_repository.update_day_schedule(
                    existing,
                    check_in_time=check_in_time,
                    check_out_time=check_out_time
                )
                logger.info(f"Updated day schedule for period {period_id}, day {day_of_week}")
                return updated
            else:
                # Create new day schedule
                created = self.day_repository.create_day_schedule(
                    period_id, day_of_week, check_in_time, check_out_time
                )
                logger.info(f"Created day schedule for period {period_id}, day {day_of_week}")
                return created
        except Exception as e:
            error_msg = f"Error creating or updating day schedule: {e}"
            logger.error(error_msg)
            return None
    
    def delete_day_schedule(self, day_schedule_id: int) -> bool:
        """
        Delete a day schedule.
        
        Args:
            day_schedule_id (int): ID of the day schedule to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the day schedule
            day_schedule = self.day_repository.get_by_id(day_schedule_id)
            if not day_schedule:
                logger.warning(f"Day schedule with ID {day_schedule_id} not found")
                return False
                
            # Delete the day schedule
            self.day_repository.delete(day_schedule)
            logger.info(f"Deleted day schedule with ID {day_schedule_id}")
            return True
        except Exception as e:
            error_msg = f"Error deleting day schedule: {e}"
            logger.error(error_msg)
            return False
    
    def get_schedule_times_for_date(self, target_date: date, user_id: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Get check-in and check-out times for a specific date.
        Prioritizes DayOverride over regular schedule.
        
        Args:
            target_date (date): The date to check
            user_id (Optional[int]): User ID
            
        Returns:
            Tuple[Optional[str], Optional[str]]: Check-in time and check-out time, or (None, None) if not found
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            if user_id is None:
                logger.warning("No user_id provided for get_schedule_times_for_date")
                return None, None
                
            # First check for override
            override_repo = DayOverrideRepository()
            override = override_repo.get_by_user_and_date(user_id, target_date)
            if override:
                logger.info(f"Found override for date {target_date}: {override.check_in_time} - {override.check_out_time}")
                return override.check_in_time, override.check_out_time
                
            # If no override, get active period for the date
            active_period = self.get_active_period_for_date(target_date, user_id)
            if not active_period:
                logger.info(f"No active period found for date {target_date} and user {user_id}")
                return None, None
                
            # Get day schedule for the weekday
            weekday = target_date.weekday()
            day_schedule = self.get_day_schedule(active_period.id, weekday)
            
            if day_schedule:
                logger.info(f"Found schedule times for date {target_date}: {day_schedule.check_in_time} - {day_schedule.check_out_time}")
                return day_schedule.check_in_time, day_schedule.check_out_time
            else:
                logger.info(f"No day schedule found for date {target_date} (weekday {weekday})")
                return None, None
        except Exception as e:
            error_msg = f"Error getting schedule times for date: {e}"
            logger.error(error_msg)
            return None, None
    
    def duplicate_period(self, period_id: int, new_name: str, new_start_date: date, 
                       new_end_date: date, user_id: Optional[int] = None) -> Optional[SchedulePeriod]:
        """
        Duplicate a schedule period with new dates.
        
        Args:
            period_id (int): ID of the period to duplicate
            new_name (str): Name for the new period
            new_start_date (date): Start date for the new period
            new_end_date (date): End date for the new period
            user_id (Optional[int]): User ID to filter
            
        Returns:
            Optional[SchedulePeriod]: New schedule period, or None on error
        """
        try:
            # Use provided user_id or fallback to instance user_id
            user_id = user_id or self.user_id
            
            # Get the source period
            source_period = self.period_repository.get_by_id(period_id, user_id)
            if not source_period:
                logger.warning(f"Period with ID {period_id} not found for user {user_id}")
                return None
                
            # Check for overlap with existing periods
            if self.period_repository.check_overlap(new_start_date, new_end_date, user_id):
                logger.warning(f"Period overlap detected for user {user_id}: {new_start_date} to {new_end_date}")
                return None
                
            # Create new period
            new_period = self.period_repository.create_period(
                new_name, new_start_date, new_end_date, user_id, source_period.is_active
            )
            
            # Get day schedules from source period
            source_day_schedules = self.day_repository.get_all_by_period(source_period.id)
            
            # Create day schedules for new period
            for day_schedule in source_day_schedules:
                self.day_repository.create_day_schedule(
                    new_period.id,
                    day_schedule.day_of_week,
                    day_schedule.check_in_time,
                    day_schedule.check_out_time
                )
            
            logger.info(f"Duplicated period {source_period.name} to {new_period.name} for user {user_id}")
            return new_period
        except Exception as e:
            error_msg = f"Error duplicating period: {e}"
            logger.error(error_msg)
            return None
    
    def copy_day_schedules(self, source_period_id: int, target_period_id: int) -> bool:
        """
        Copy day schedules from one period to another.
        
        Args:
            source_period_id (int): Source period ID
            target_period_id (int): Target period ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get source day schedules
            source_day_schedules = self.day_repository.get_all_by_period(source_period_id)
            if not source_day_schedules:
                logger.warning(f"No day schedules found for source period {source_period_id}")
                return False
            
            # Get target period
            target_period = self.period_repository.get_by_id(target_period_id)
            if not target_period:
                logger.warning(f"Target period with ID {target_period_id} not found")
                return False
                
            # Delete existing day schedules in target period
            existing_target_day_schedules = self.day_repository.get_all_by_period(target_period_id)
            for day_schedule in existing_target_day_schedules:
                self.day_repository.delete(day_schedule)
                
            # Copy day schedules to target period
            for day_schedule in source_day_schedules:
                self.day_repository.create_day_schedule(
                    target_period_id,
                    day_schedule.day_of_week,
                    day_schedule.check_in_time,
                    day_schedule.check_out_time
                )
                
            logger.info(f"Copied {len(source_day_schedules)} day schedules from period {source_period_id} to {target_period_id}")
            return True
        except Exception as e:
            error_msg = f"Error copying day schedules: {e}"
            logger.error(error_msg)
            return False 
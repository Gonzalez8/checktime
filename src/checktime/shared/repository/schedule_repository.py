"""
Repository for schedule operations.
"""

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import and_

from checktime.shared.db import db
from checktime.shared.models.schedule import SchedulePeriod, DaySchedule
from checktime.shared.repository.base_repository import BaseRepository

class SchedulePeriodRepository(BaseRepository[SchedulePeriod]):
    """Repository for schedule period operations."""
    
    def __init__(self):
        """Initialize the repository."""
        super().__init__(SchedulePeriod)
    
    def get_all(self, user_id: int = None) -> List[SchedulePeriod]:
        """Get all schedule periods, optionally filtering by user."""
        query = SchedulePeriod.query
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.order_by(SchedulePeriod.start_date).all()
    
    def get_by_id(self, id: int, user_id: int = None) -> Optional[SchedulePeriod]:
        """Get a schedule period by ID, optionally filtering by user."""
        query = SchedulePeriod.query.filter_by(id=id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.first()
    
    def get_active_periods(self, user_id: int = None) -> List[SchedulePeriod]:
        """Get all active schedule periods for a specific user."""
        query = SchedulePeriod.query.filter_by(is_active=True)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.order_by(SchedulePeriod.start_date).all()
    
    def get_active_periods_after_date(self, target_date: date, user_id: int = None) -> List[SchedulePeriod]:
        """Get all active schedule periods that end after the specified date for a specific user."""
        query = SchedulePeriod.query.filter(
            SchedulePeriod.is_active == True,
            SchedulePeriod.end_date >= target_date
        )
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.order_by(SchedulePeriod.start_date).all()
    
    def get_periods_for_date_range(self, start_date: date, end_date: date, user_id: int = None) -> List[SchedulePeriod]:
        """Get all periods that overlap with the given date range for a specific user."""
        query = SchedulePeriod.query.filter(
            SchedulePeriod.is_active == True,
            SchedulePeriod.end_date >= start_date,
            SchedulePeriod.start_date <= end_date
        )
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.order_by(SchedulePeriod.start_date).all()
    
    def get_active_period_for_date(self, target_date: date, user_id: int = None) -> Optional[SchedulePeriod]:
        """Get active schedule period for a specific date and user."""
        query = SchedulePeriod.query.filter(
            SchedulePeriod.is_active == True,
            SchedulePeriod.start_date <= target_date,
            SchedulePeriod.end_date >= target_date
        )
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.first()
    
    def create_period(self, name: str, start_date: date, end_date: date, user_id: int, is_active: bool = True) -> SchedulePeriod:
        """Create a new schedule period for a specific user."""
        period = SchedulePeriod(
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            user_id=user_id
        )
        return super().create(period)
    
    def update_period(self, period: SchedulePeriod, name: str = None, start_date: date = None, 
                      end_date: date = None, is_active: bool = None) -> SchedulePeriod:
        """Update a schedule period."""
        if name:
            period.name = name
        if start_date:
            period.start_date = start_date
        if end_date:
            period.end_date = end_date
        if is_active is not None:
            period.is_active = is_active
        return super().update(period)
    
    def check_overlap(self, start_date: date, end_date: date, user_id: int, exclude_id: Optional[int] = None) -> bool:
        """Check if there's an overlap with existing periods for a specific user."""
        query = SchedulePeriod.query.filter(
            and_(
                SchedulePeriod.end_date >= start_date,
                SchedulePeriod.start_date <= end_date,
                SchedulePeriod.user_id == user_id
            )
        )
        
        if exclude_id:
            query = query.filter(SchedulePeriod.id != exclude_id)
            
        return query.first() is not None


class DayScheduleRepository(BaseRepository[DaySchedule]):
    """Repository for day schedule operations."""
    
    def __init__(self):
        """Initialize the repository."""
        super().__init__(DaySchedule)
    
    def get_by_period_and_day(self, period_id: int, day_of_week: int) -> Optional[DaySchedule]:
        """Get a day schedule by period ID and day of week."""
        return DaySchedule.query.filter_by(
            period_id=period_id,
            day_of_week=day_of_week
        ).first()
    
    def get_all_by_period(self, period_id: int) -> List[DaySchedule]:
        """Get all day schedules for a period."""
        return DaySchedule.query.filter_by(period_id=period_id).order_by(DaySchedule.day_of_week).all()
    
    def create_day_schedule(self, period_id: int, day_of_week: int, 
                         check_in_time: str, check_out_time: str) -> DaySchedule:
        """Create a new day schedule."""
        day_schedule = DaySchedule(
            period_id=period_id,
            day_of_week=day_of_week,
            check_in_time=check_in_time,
            check_out_time=check_out_time
        )
        return super().create(day_schedule)
    
    def update_day_schedule(self, day_schedule: DaySchedule, day_of_week: int = None,
                         check_in_time: str = None, check_out_time: str = None) -> DaySchedule:
        """Update a day schedule."""
        if day_of_week is not None:
            day_schedule.day_of_week = day_of_week
        if check_in_time:
            day_schedule.check_in_time = check_in_time
        if check_out_time:
            day_schedule.check_out_time = check_out_time
        return super().update(day_schedule)
    
    def get_schedule_times_for_date(self, target_date: date, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        """Get check-in and check-out times for a specific date based on the active schedule for a user."""
        weekday = target_date.weekday()
        
        # Get active period for the target date and user
        period_repo = SchedulePeriodRepository()
        active_period = period_repo.get_active_period_for_date(target_date, user_id)
        
        if active_period:
            # Get day schedule for the weekday
            day_schedule = self.get_by_period_and_day(active_period.id, weekday)
            
            if day_schedule:
                return day_schedule.check_in_time, day_schedule.check_out_time
        
        return None, None 
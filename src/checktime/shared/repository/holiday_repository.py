"""
Repository for holiday operations.
"""

from datetime import datetime
from typing import List, Optional

from checktime.shared.db import db
from checktime.shared.models.holiday import Holiday
from checktime.shared.repository.base_repository import BaseRepository

class HolidayRepository(BaseRepository[Holiday]):
    """Repository for holiday operations."""
    
    def __init__(self):
        """Initialize the repository."""
        super().__init__(Holiday)
    
    def get_all(self, user_id: int) -> List[Holiday]:
        """Get all holidays for a specific user."""
        return Holiday.query.filter_by(user_id=user_id).order_by(Holiday.date).all()
    
    def get_by_id(self, id: int, user_id: int = None) -> Optional[Holiday]:
        """Get a holiday by ID, optionally filtering by user_id."""
        query = Holiday.query.filter_by(id=id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.first()
    
    def get_by_date(self, date: datetime.date, user_id: int) -> Optional[Holiday]:
        """Get a holiday by date for a specific user."""
        return Holiday.query.filter_by(date=date, user_id=user_id).first()
    
    def create(self, date: datetime.date, description: str, user_id: int) -> Holiday:
        """Create a new holiday for a specific user."""
        holiday = Holiday(date=date, description=description, user_id=user_id)
        return super().create(holiday)
    
    def update(self, holiday: Holiday, date: datetime.date = None, description: str = None) -> Holiday:
        """Update a holiday."""
        if date:
            holiday.date = date
        if description:
            holiday.description = description
        return super().update(holiday)
    
    def delete(self, holiday: Holiday) -> None:
        """Delete a holiday."""
        return super().delete(holiday)
    
    def get_all_dates(self, user_id: int) -> List[str]:
        """Get all holiday dates as strings (YYYY-MM-DD) for a specific user."""
        return Holiday.get_all_dates(user_id)
        
    def get_upcoming_holidays(self, start_date: datetime.date, limit: int = 5, user_id: int = None) -> List[Holiday]:
        """Get upcoming holidays starting from a specific date for a specific user."""
        query = Holiday.query.filter(Holiday.date >= start_date)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.order_by(Holiday.date).limit(limit).all()
        
    def get_holidays_for_date_range(self, start_date: datetime.date, end_date: datetime.date, user_id: int = None) -> List[Holiday]:
        """Get all holidays within a date range for a specific user."""
        query = Holiday.query.filter(
            Holiday.date >= start_date,
            Holiday.date <= end_date
        )
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.all() 
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
    
    def get_all(self) -> List[Holiday]:
        """Get all holidays."""
        return Holiday.query.order_by(Holiday.date).all()
    
    def get_by_id(self, id: int) -> Optional[Holiday]:
        """Get a holiday by ID."""
        return Holiday.query.get(id)
    
    def get_by_date(self, date: datetime.date) -> Optional[Holiday]:
        """Get a holiday by date."""
        return Holiday.query.filter_by(date=date).first()
    
    def create(self, date: datetime.date, description: str) -> Holiday:
        """Create a new holiday."""
        holiday = Holiday(date=date, description=description)
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
    
    def get_all_dates(self) -> List[str]:
        """Get all holiday dates as strings (YYYY-MM-DD)."""
        return Holiday.get_all_dates()
        
    def get_upcoming_holidays(self, start_date: datetime.date, limit: int = 5) -> List[Holiday]:
        """Get upcoming holidays starting from a specific date."""
        return Holiday.query.filter(
            Holiday.date >= start_date
        ).order_by(Holiday.date).limit(limit).all()
        
    def get_holidays_for_date_range(self, start_date: datetime.date, end_date: datetime.date) -> List[Holiday]:
        """Get all holidays within a date range."""
        return Holiday.query.filter(
            Holiday.date >= start_date,
            Holiday.date <= end_date
        ).all() 
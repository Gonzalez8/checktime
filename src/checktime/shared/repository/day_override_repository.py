"""
Repository for managing DayOverride entities.
"""

from datetime import date
from typing import List, Optional

from checktime.shared.models.schedule import DayOverride
from checktime.shared.repository.base_repository import BaseRepository

class DayOverrideRepository(BaseRepository[DayOverride]):
    """Repository for managing DayOverride entities."""
    
    def __init__(self):
        super().__init__(DayOverride)
    
    def get_by_user_and_date(self, user_id: int, target_date: date) -> Optional[DayOverride]:
        """Get a day override for a specific user and date."""
        return DayOverride.query.filter_by(
            user_id=user_id,
            date=target_date
        ).first()
    
    def get_by_user_in_date_range(self, user_id: int, start_date: date, end_date: date) -> List[DayOverride]:
        """Get all day overrides for a user within a date range."""
        return DayOverride.query.filter(
            DayOverride.user_id == user_id,
            DayOverride.date >= start_date,
            DayOverride.date <= end_date
        ).all()
    
    def delete_by_user_and_date(self, user_id: int, target_date: date) -> bool:
        """Delete a day override for a specific user and date."""
        override = self.get_by_user_and_date(user_id, target_date)
        if override:
            self.delete(override)
            return True
        return False 
"""
Repository module for database operations.
"""

from checktime.shared.repository.base_repository import BaseRepository
from checktime.shared.repository.holiday_repository import HolidayRepository
from checktime.shared.repository.user_repository import UserRepository
from checktime.shared.repository.schedule_repository import SchedulePeriodRepository, DayScheduleRepository
from checktime.shared.repository.day_override_repository import DayOverrideRepository

# Create singleton instances for easy access
holiday_repository = HolidayRepository()
user_repository = UserRepository()
schedule_period_repository = SchedulePeriodRepository()
day_schedule_repository = DayScheduleRepository() 
from datetime import datetime, date
import calendar

from checktime.shared.services.holiday_manager import HolidayManager
from checktime.shared.services.schedule_manager import ScheduleManager
from checktime.shared.services.day_override_manager import DayOverrideManager

def generate_calendar_data(year, month, active_periods, user_id):
    """Generate calendar data for the specified month for all active periods.
    
    Args:
        year: The year (e.g., 2023)
        month: The month (1-12)
        active_periods: List of active schedule periods to include in the calendar
        user_id: The ID of the user
        
    Returns:
        A list of weeks, where each week is a list of days. Each day is a dictionary
        containing information about that day.
    """
    # Get the first day of the month and the number of days
    first_day = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    
    # Get all holidays for this month
    start_date = first_day
    end_date = date(year, month, num_days)
    
    # Initialize managers
    holiday_manager = HolidayManager(user_id)
    schedule_manager = ScheduleManager(user_id)
    override_manager = DayOverrideManager(user_id)
    
    # Get holidays for the month
    holidays = holiday_manager.get_holidays_for_date_range(start_date, end_date)
    
    # Get overrides for the month
    overrides = override_manager.get_overrides_in_range(start_date, end_date)
    overrides_by_date = {override.date: override for override in overrides}
    
    # Create a dictionary of holidays for quick lookup
    holiday_dict = {h.date: h for h in holidays}
    
    # Get working days from all active periods
    working_days = {}  # Dictionary to store working days with their schedules
    
    # Process each active period
    for period in active_periods:
        # Check if this month overlaps with the schedule period
        if not (end_date < period.start_date or start_date > period.end_date):
            # Get all day schedules for this period
            day_schedules = schedule_manager.get_all_day_schedules(period.id)
            
            # Build a dictionary of daily schedules for this period
            schedule_dict = {day_schedule.day_of_week: day_schedule for day_schedule in day_schedules}
            
            # For each day in the month
            for day in range(1, num_days + 1):
                check_date = date(year, month, day)
                
                # Skip if outside schedule range
                if check_date < period.start_date or check_date > period.end_date:
                    continue
                
                # Skip if not in schedule
                if check_date.weekday() not in schedule_dict:
                    continue
                
                # Skip if it's a holiday
                if check_date in holiday_dict:
                    continue
                
                # Skip if it has an override (will be handled separately)
                if check_date in overrides_by_date:
                    continue
                
                # If we get here, it's a working day - add to our dictionary
                day_schedule = schedule_dict[check_date.weekday()]
                working_days[check_date] = {
                    'check_in_time': day_schedule.check_in_time,
                    'check_out_time': day_schedule.check_out_time,
                    'period_name': period.name
                }
    
    # Generate the calendar data
    calendar_days = []
    month_calendar = calendar.monthcalendar(year, month)
    today = datetime.now().date()
    
    for week in month_calendar:
        week_data = []
        for day in week:
            if day == 0:
                # Day outside the month
                week_data.append({
                    'day': None,
                    'date': None,
                    'is_today': False,
                    'is_holiday': False,
                    'is_working_day': False,
                    'is_override': False,
                    'holiday_name': None,
                    'check_in_time': None,
                    'check_out_time': None,
                    'period_name': None,
                    'override_description': None
                })
            else:
                check_date = date(year, month, day)
                is_holiday = check_date in holiday_dict
                is_working_day = check_date in working_days
                is_override = check_date in overrides_by_date
                
                # Default values
                check_in_time = None
                check_out_time = None
                period_name = None
                override_description = None
                
                # Check for override first (priority over regular schedules)
                if is_override:
                    override = overrides_by_date[check_date]
                    check_in_time = override.check_in_time
                    check_out_time = override.check_out_time
                    override_description = override.description
                    is_working_day = False  # Override replaces regular working day
                # If not override but a working day, get regular schedule
                elif is_working_day:
                    check_in_time = working_days[check_date]['check_in_time']
                    check_out_time = working_days[check_date]['check_out_time']
                    period_name = working_days[check_date]['period_name']
                
                day_data = {
                    'day': day,
                    'date': check_date.strftime('%Y-%m-%d'),  # Ensure date is always set for valid days
                    'is_today': check_date == today,
                    'is_holiday': is_holiday,
                    'is_working_day': is_working_day,
                    'is_override': is_override,
                    'holiday_name': holiday_dict[check_date].description if is_holiday else None,
                    'check_in_time': check_in_time,
                    'check_out_time': check_out_time,
                    'period_name': period_name,
                    'override_description': override_description
                }
                week_data.append(day_data)
        calendar_days.append(week_data)
    
    return calendar_days 
from datetime import datetime, date, timedelta
import calendar
from flask import Blueprint, render_template, g, url_for
from flask_login import login_required, current_user

from checktime.shared.services.schedule_manager import ScheduleManager
from checktime.shared.services.holiday_manager import HolidayManager
from checktime.shared.services.day_override_manager import DayOverrideManager
from checktime.web.translations import get_translation
from checktime.web.utils.calendar_utils import generate_calendar_data

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@dashboard_bp.route('/calendar/<int:year>/<int:month>')
@login_required
def index(year=None, month=None):
    """Dashboard home page showing summary of configurations."""
    # Initialize the date
    today = datetime.now().date()
    
    # Default to current month/year if not provided
    if not year or not month:
        year = today.year
        month = today.month
    
    # Validate month value
    if month < 1 or month > 12:
        month = today.month
    
    # Create the selected date
    current_date = date(year, month, 1)
    
    # Calculate start and end of current week
    current_weekday = today.weekday()
    start_of_week = today - timedelta(days=current_weekday)
    end_of_week = start_of_week + timedelta(days=6)
    
    # Calculate previous and next month
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
        
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    # Get the last day of the month
    last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
    
    # Initialize managers
    schedule_manager = ScheduleManager(current_user.id)
    holiday_manager = HolidayManager(current_user.id)
    override_manager = DayOverrideManager(current_user.id)
    
    # Get upcoming holidays (next 30 days)
    future_date = today + timedelta(days=30)
    upcoming_holidays = holiday_manager.get_holidays_for_date_range(today, future_date)
    
    # Get active schedule periods
    active_periods = schedule_manager.get_active_periods(current_user.id)
    
    # Get the current schedule period (if any)
    current_schedule = None
    for period in active_periods:
        if period.start_date <= today <= period.end_date:
            current_schedule = period
            break
    
    # Get the day schedules for the current period
    day_schedules = []
    if current_schedule:
        day_schedules = schedule_manager.get_all_day_schedules(current_schedule.id)
    
    # Count working days this week
    days_this_week = 0
    
    # If we have a current schedule, count days based on schedule
    if current_schedule and day_schedules:
        # Create a set of days of the week that are working days
        working_weekdays = {day_schedule.day_of_week for day_schedule in day_schedules}
        
        # Get holidays for the current week
        week_holidays = holiday_manager.get_holidays_for_date_range(start_of_week, end_of_week)
        holiday_dates = {h.date for h in week_holidays}
        
        # Get overrides for the current week
        week_overrides = override_manager.get_overrides_in_range(start_of_week, end_of_week)
        override_dates = {o.date for o in week_overrides}
        
        # Count days
        current_day = start_of_week
        while current_day <= end_of_week:
            # If there's an override for this day, it's a working day
            if current_day in override_dates:
                days_this_week += 1
            # Otherwise check if this is a regular working day (in schedule and not a holiday)
            elif current_day.weekday() in working_weekdays and current_day not in holiday_dates:
                days_this_week += 1
            current_day += timedelta(days=1)
    
    # Get all active schedule periods that overlap with the selected month
    month_periods = schedule_manager.get_periods_for_date_range(current_date, last_day_of_month, current_user.id)
    
    # Generate calendar data using the shared function
    calendar_data = generate_calendar_data(year, month, month_periods, current_user.id)
    
    # Format month name
    month_name = current_date.strftime('%B %Y')
    
    # Add URLs for JavaScript API calls
    holiday_api_url = url_for('holidays.api_add')
    calendar_partial_url = url_for('dashboard.calendar_partial', year=0, month=0)
    
    return render_template('dashboard/index.html',
                         calendar_data=calendar_data,
                         current_month=month_name,
                         current_month_num=month,
                         current_year=year,
                         prev_month=prev_month,
                         prev_year=prev_year,
                         next_month=next_month,
                         next_year=next_year,
                         is_current_month=(year == today.year and month == today.month),
                         upcoming_holidays=upcoming_holidays,
                         active_periods=active_periods,
                         current_schedule=current_schedule,
                         day_schedules=day_schedules,
                         days_this_week=days_this_week,
                         today=today,
                         api_holiday_url=holiday_api_url,
                         calendar_partial_url=calendar_partial_url)

@dashboard_bp.route('/calendar-partial/<int:year>/<int:month>')
@login_required
def calendar_partial(year, month):
    """Return only the calendar HTML without reloading the entire page."""
    today = datetime.now().date()
    
    # Validate month value
    if month < 1 or month > 12:
        month = today.month
    
    # Create the selected date
    current_date = date(year, month, 1)
    last_day_of_month = date(year, month, calendar.monthrange(year, month)[1])
    
    # Calculate previous and next month
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
        
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    # Initialize manager
    schedule_manager = ScheduleManager(current_user.id)
    
    # Get all active schedule periods that overlap with the selected month
    active_periods = schedule_manager.get_periods_for_date_range(current_date, last_day_of_month, current_user.id)
    
    # Generate calendar data for all active periods that overlap with this month
    calendar_data = generate_calendar_data(year, month, active_periods, current_user.id)
    
    # Get the month name in the appropriate language
    month_name = current_date.strftime('%B')
    lang = getattr(g, 'language', 'en')
    month_key = f'month_{month_name.lower()}'
    month_translation = get_translation(month_key, lang)
    
    return render_template(
        'dashboard/calendar_partial.html',
        calendar_data=calendar_data,
        current_month=f"{month_translation} {year}",
        current_month_num=today.month,
        current_year=today.year,
        is_current_month=(year == today.year and month == today.month),
        year=year,
        month=month,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )

@dashboard_bp.route('/upcoming-holidays-partial')
@login_required
def upcoming_holidays_partial():
    """Return only the upcoming holidays HTML without reloading the entire page."""
    today = datetime.now().date()
    
    # Get upcoming holidays (next 30 days)
    future_date = today + timedelta(days=30)
    
    # Initialize holiday manager
    holiday_manager = HolidayManager(current_user.id)
    
    # Get upcoming holidays
    upcoming_holidays = holiday_manager.get_holidays_for_date_range(today, future_date)
    
    return render_template(
        'dashboard/upcoming_holidays_partial.html',
        upcoming_holidays=upcoming_holidays,
        today=today
    ) 
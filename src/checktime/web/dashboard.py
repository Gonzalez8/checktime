from flask import Blueprint, render_template, request, jsonify, g
from flask_login import login_required, current_user

from checktime.shared.services.holiday_manager import HolidayManager
from checktime.shared.services.schedule_manager import ScheduleManager
from datetime import datetime, timedelta, date
import calendar
from checktime.web.translations import get_translation

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@dashboard_bp.route('/calendar/<int:year>/<int:month>')
@login_required
def index(year=None, month=None):
    """Dashboard home page showing summary of configurations."""
    # Get today's date for default values
    today = datetime.now().date()
    
    # Use provided year and month or defaults
    if year is None or month is None:
        year = today.year
        month = today.month
    
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
    
    # Initialize managers
    holiday_manager = HolidayManager(current_user.id)
    schedule_manager = ScheduleManager(current_user.id)
    
    # Get holidays - now directly using Holiday objects with days_remaining attribute
    upcoming_holidays = holiday_manager.get_upcoming_holidays()[:5]
    
    # Get active schedule periods
    active_periods = schedule_manager.get_active_periods_after_date(today)
    
    # Get current schedule
    current_schedule = next((period for period in active_periods 
                      if period.start_date <= today <= period.end_date), None)
    
    # Get day schedules if current schedule exists
    day_schedules = []
    if current_schedule:
        day_schedules = sorted(schedule_manager.get_all_day_schedules(current_schedule.id), 
                              key=lambda x: x.day_of_week)
    
    # Weekly stats: number of working days
    # Calculate start and end of current week
    weekday = today.weekday()
    start_of_week = today - timedelta(days=weekday)
    end_of_week = start_of_week + timedelta(days=6)  # Sunday
    
    days_this_week = 0
    
    # Get holidays for this week
    week_holidays = holiday_manager.get_holidays_for_date_range(start_of_week, end_of_week)
    holiday_dates = [h.date for h in week_holidays]
    
    # Count working days (weekdays with schedule that are not holidays)
    if current_schedule:
        # Get all days with schedules for this period
        day_schedules_dict = schedule_manager.get_all_day_schedules(current_schedule.id)
        scheduled_days = [day.day_of_week for day in day_schedules_dict]
        
        for i in range(7):
            check_date = start_of_week + timedelta(days=i)
            # Skip days outside of schedule date range
            if check_date < current_schedule.start_date or check_date > current_schedule.end_date:
                continue
            # Skip holidays
            if check_date in holiday_dates:
                continue
            # Skip days without schedule
            if check_date.weekday() not in scheduled_days:
                continue
            # If we get here, it's a working day
            if check_date >= today:
                days_this_week += 1
    
    # Get all active periods that overlap with the selected month for the calendar
    calendar_active_periods = schedule_manager.get_periods_for_date_range(current_date, last_day_of_month)
    
    # Generate calendar data for the selected month
    calendar_data = generate_calendar_data(year, month, calendar_active_periods, current_user.id)
    
    # Get the month name in the appropriate language
    month_name = current_date.strftime('%B')
    lang = getattr(g, 'language', 'en')
    month_key = f'month_{month_name.lower()}'
    month_translation = get_translation(month_key, lang)
    
    return render_template(
        'dashboard/index.html',
        title='Dashboard',
        upcoming_holidays=upcoming_holidays,
        active_periods=active_periods,
        current_schedule=current_schedule,
        day_schedules=day_schedules,
        days_this_week=days_this_week,
        today=today,
        calendar_data=calendar_data,
        current_month=f"{month_translation} {year}",
        is_current_month=(year == today.year and month == today.month),
        current_year=year,
        current_month_num=month,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )

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
    active_periods = schedule_manager.get_periods_for_date_range(current_date, last_day_of_month)
    
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

def generate_calendar_data(year, month, active_periods, user_id):
    """Generate calendar data for the specified month for all active periods."""
    # Get the first day of the month and the number of days
    first_day = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    
    # Get all holidays for this month
    start_date = first_day
    end_date = date(year, month, num_days)
    
    # Initialize managers
    holiday_manager = HolidayManager(user_id)
    schedule_manager = ScheduleManager(user_id)
    
    holidays = holiday_manager.get_holidays_for_date_range(start_date, end_date)
    
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
    
    for week in month_calendar:
        week_data = []
        for day in week:
            if day == 0:
                # Day outside the month
                week_data.append({
                    'day': None,
                    'is_today': False,
                    'is_holiday': False,
                    'is_working_day': False,
                    'holiday_name': None,
                    'check_in_time': None,
                    'check_out_time': None,
                    'period_name': None
                })
            else:
                check_date = date(year, month, day)
                today = datetime.now().date()
                is_holiday = check_date in holiday_dict
                is_working_day = check_date in working_days
                
                # Get schedule times if this is a working day
                check_in_time = None
                check_out_time = None
                period_name = None
                if is_working_day:
                    check_in_time = working_days[check_date]['check_in_time']
                    check_out_time = working_days[check_date]['check_out_time']
                    period_name = working_days[check_date]['period_name']
                
                week_data.append({
                    'day': day,
                    'is_today': check_date == today,
                    'is_holiday': is_holiday,
                    'is_working_day': is_working_day,
                    'holiday_name': holiday_dict[check_date].description if is_holiday else None,
                    'check_in_time': check_in_time,
                    'check_out_time': check_out_time,
                    'period_name': period_name
                })
        calendar_days.append(week_data)
    
    return calendar_days 
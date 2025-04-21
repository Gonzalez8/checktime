from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from checktime.web.models import Holiday, SchedulePeriod, DaySchedule
from datetime import datetime, timedelta, date
import calendar

dashboard_bp = Blueprint('dashboard', __name__)

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
    
    # Get holidays
    upcoming_holidays = Holiday.query.filter(Holiday.date >= today).order_by(Holiday.date).limit(5).all()
    
    # Get active schedule periods
    active_periods = SchedulePeriod.query.filter(
        SchedulePeriod.is_active == True,
        SchedulePeriod.end_date >= today
    ).order_by(SchedulePeriod.start_date).all()
    
    # Get current schedule
    current_schedule = None
    for period in active_periods:
        if period.start_date <= today <= period.end_date:
            current_schedule = period
            break
    
    # Get day schedules if current schedule exists
    day_schedules = []
    if current_schedule:
        day_schedules = sorted(current_schedule.schedules, key=lambda x: x.day_of_week)
    
    # Weekly stats: number of working days
    # Calculate start and end of current week
    weekday = today.weekday()
    start_of_week = today - timedelta(days=weekday)
    end_of_week = start_of_week + timedelta(days=6)  # Sunday
    
    days_this_week = 0
    
    # Get holidays for this week
    week_holidays = Holiday.query.filter(
        Holiday.date >= start_of_week,
        Holiday.date <= end_of_week
    ).all()
    holiday_dates = [h.date for h in week_holidays]
    
    # Count working days (weekdays with schedule that are not holidays)
    if current_schedule:
        scheduled_days = [day.day_of_week for day in current_schedule.schedules]
        
        for i in range(7):
            check_date = start_of_week + timedelta(days=i)
            # Skip days outside of schedule date range
            if check_date < current_schedule.start_date or check_date > current_schedule.end_date:
                continue
            # Skip weekends (5=Sat, 6=Sun)
            if check_date.weekday() >= 5:
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
    
    # Generate calendar data for the selected month
    calendar_data = generate_calendar_data(year, month, current_schedule)
    
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
        current_month=current_date.strftime('%B %Y'),
        is_current_month=(year == today.year and month == today.month),
        year=year,
        month=month,
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
    
    # Get current schedule
    active_periods = SchedulePeriod.query.filter(
        SchedulePeriod.is_active == True,
        SchedulePeriod.end_date >= today
    ).order_by(SchedulePeriod.start_date).all()
    
    current_schedule = None
    for period in active_periods:
        if period.start_date <= today <= period.end_date:
            current_schedule = period
            break
    
    # Generate calendar data for the selected month
    calendar_data = generate_calendar_data(year, month, current_schedule)
    
    return render_template(
        'dashboard/calendar_partial.html',
        calendar_data=calendar_data,
        current_month=current_date.strftime('%B %Y'),
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

def generate_calendar_data(year, month, current_schedule):
    """Generate calendar data for the specified month."""
    # Get the first day of the month and the number of days
    first_day = date(year, month, 1)
    _, num_days = calendar.monthrange(year, month)
    
    # Get all holidays for this month
    start_date = first_day
    end_date = date(year, month, num_days)
    
    holidays = Holiday.query.filter(
        Holiday.date >= start_date,
        Holiday.date <= end_date
    ).all()
    
    # Create a dictionary of holidays for quick lookup
    holiday_dict = {h.date: h for h in holidays}
    
    # Get working day configuration if we have a schedule
    working_days = set()
    if current_schedule:
        # Check if this month overlaps with the schedule
        if not (end_date < current_schedule.start_date or start_date > current_schedule.end_date):
            # Get the days of the week that are configured as working days
            scheduled_days = [day.day_of_week for day in current_schedule.schedules]
            
            # For each day in the month
            for day in range(1, num_days + 1):
                check_date = date(year, month, day)
                
                # Skip if outside schedule range
                if check_date < current_schedule.start_date or check_date > current_schedule.end_date:
                    continue
                
                # Skip weekends
                if check_date.weekday() >= 5:
                    continue
                
                # Skip if not in schedule
                if check_date.weekday() not in scheduled_days:
                    continue
                
                # Skip if it's a holiday
                if check_date in holiday_dict:
                    continue
                
                # If we get here, it's a working day
                working_days.add(check_date)
    
    # Build a dictionary of daily schedules for quicker lookup
    schedule_dict = {}
    if current_schedule:
        day_schedules = current_schedule.schedules
        for day_schedule in day_schedules:
            schedule_dict[day_schedule.day_of_week] = day_schedule
    
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
                    'check_out_time': None
                })
            else:
                check_date = date(year, month, day)
                today = datetime.now().date()
                is_holiday = check_date in holiday_dict
                is_working_day = check_date in working_days
                
                # Get schedule times if this is a working day
                check_in_time = None
                check_out_time = None
                if is_working_day and check_date.weekday() in schedule_dict:
                    day_schedule = schedule_dict[check_date.weekday()]
                    check_in_time = day_schedule.check_in_time
                    check_out_time = day_schedule.check_out_time
                
                week_data.append({
                    'day': day,
                    'is_today': check_date == today,
                    'is_holiday': is_holiday,
                    'is_working_day': is_working_day,
                    'holiday_name': holiday_dict[check_date].description if is_holiday else None,
                    'check_in_time': check_in_time,
                    'check_out_time': check_out_time
                })
        calendar_days.append(week_data)
    
    return calendar_days 
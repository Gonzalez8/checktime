from flask import Blueprint, render_template
from flask_login import login_required, current_user

from checktime.web.models import Holiday, SchedulePeriod, DaySchedule
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard home page showing summary of configurations."""
    # Get holidays
    today = datetime.now().date()
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
    
    return render_template(
        'dashboard/index.html',
        title='Dashboard',
        upcoming_holidays=upcoming_holidays,
        active_periods=active_periods,
        current_schedule=current_schedule,
        day_schedules=day_schedules,
        days_this_week=days_this_week,
        today=today
    ) 
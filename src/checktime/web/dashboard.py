from flask import Blueprint, render_template
from flask_login import login_required, current_user

from checktime.web.models import Holiday, SchedulePeriod
from datetime import datetime

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
    weekday = today.weekday()
    days_this_week = 5 - weekday if weekday < 5 else 0
    
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
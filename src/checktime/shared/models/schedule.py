"""
Schedule models for CheckTime.
"""

from checktime.shared.db import db, TimestampMixin
from sqlalchemy import UniqueConstraint

class SchedulePeriod(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    schedules = db.relationship('DaySchedule', backref='period', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SchedulePeriod {self.name}: {self.start_date} to {self.end_date}>"

class DaySchedule(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('schedule_period.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    check_in_time = db.Column(db.String(5), nullable=False)  # Format: "09:00"
    check_out_time = db.Column(db.String(5), nullable=False)  # Format: "18:00"
    
    @property
    def day_name(self):
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return days[self.day_of_week]
    
    def __repr__(self):
        return f"<DaySchedule {self.day_name}: {self.check_in_time} - {self.check_out_time}>"

class DayOverride(db.Model, TimestampMixin):
    """
    Represents a schedule override for a specific date and user.
    This takes precedence over the regular DaySchedule.
    """
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.String(5), nullable=False)  # Format: "09:00"
    check_out_time = db.Column(db.String(5), nullable=False)  # Format: "18:00"
    description = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Ensure only one override per user per date
    __table_args__ = (UniqueConstraint('user_id', 'date', name='uq_user_date_override'),)
    
    def __repr__(self):
        return f"<DayOverride {self.date}: {self.check_in_time} - {self.check_out_time}>" 
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Holiday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    @property
    def date_str(self):
        return self.date.strftime("%Y-%m-%d")
    
    @classmethod
    def get_all_dates(cls):
        return [holiday.date_str for holiday in cls.query.all()]

class SchedulePeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    schedules = db.relationship('DaySchedule', backref='period', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SchedulePeriod {self.name}: {self.start_date} to {self.end_date}>"

class DaySchedule(db.Model):
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
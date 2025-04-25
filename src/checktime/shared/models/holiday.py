"""
Holiday model for CheckTime.
"""

from checktime.shared.db import db, TimestampMixin

class Holiday(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    description = db.Column(db.String(200))
    
    @property
    def date_str(self):
        return self.date.strftime("%Y-%m-%d")
    
    @classmethod
    def get_all_dates(cls):
        return [holiday.date_str for holiday in cls.query.all()] 
"""
Holiday model for CheckTime.
"""

from checktime.shared.db import db, TimestampMixin
from sqlalchemy import UniqueConstraint

class Holiday(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # A date can be a holiday for multiple users, but must be unique per user
    __table_args__ = (UniqueConstraint('date', 'user_id', name='_date_user_uc'),)
    
    @property
    def date_str(self):
        return self.date.strftime("%Y-%m-%d")
    
    @classmethod
    def get_all_dates(cls, user_id):
        return [holiday.date_str for holiday in cls.query.filter_by(user_id=user_id).all()] 
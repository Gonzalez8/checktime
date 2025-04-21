from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, timedelta

from checktime.web.models import db, Holiday
from checktime.fichaje.holidays import HolidayManager

holidays_bp = Blueprint('holidays', __name__, url_prefix='/holidays')

class HolidayForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Save')

class HolidayRangeForm(FlaskForm):
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Add Holidays')
    
    def validate_end_date(self, field):
        if field.data < self.start_date.data:
            raise ValidationError('End date must be after start date')

@holidays_bp.route('/')
@login_required
def index():
    """List all holidays."""
    holidays = Holiday.query.order_by(Holiday.date).all()
    return render_template('holidays/index.html', title='Holidays', holidays=holidays)

@holidays_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new holiday."""
    form = HolidayForm()
    if form.validate_on_submit():
        # Check if holiday already exists
        existing = Holiday.query.filter_by(date=form.date.data).first()
        if existing:
            flash('Holiday already exists for this date','danger')
            return redirect(url_for('holidays.index'))
        
        # Add to database
        holiday = Holiday(date=form.date.data, description=form.description.data)
        db.session.add(holiday)
        db.session.commit()
        flash('Holiday added successfully')
        return redirect(url_for('holidays.index'))
    
    return render_template('holidays/add.html', title='Add Holiday', form=form)

@holidays_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Edit an existing holiday."""
    holiday = Holiday.query.get_or_404(id)
    form = HolidayForm(obj=holiday)
    
    if form.validate_on_submit():
        holiday.date = form.date.data
        holiday.description = form.description.data
        db.session.commit()
        flash('Holiday updated successfully')
        return redirect(url_for('holidays.index'))
    
    return render_template('holidays/edit.html', title='Edit Holiday', form=form, holiday=holiday)

@holidays_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete a holiday."""
    holiday = Holiday.query.get_or_404(id)
    db.session.delete(holiday)
    db.session.commit()
    
    flash('Holiday deleted successfully')
    return redirect(url_for('holidays.index'))

@holidays_bp.route('/sync')
@login_required
def sync():
    """Update holidays in memory with current database state."""
    # Create a holiday manager instance
    holiday_manager = HolidayManager()
    
    # Get all holidays from the database
    holidays = Holiday.query.order_by(Holiday.date).all()
    
    # Clear existing holidays and add each one from the database
    holiday_manager.clear_holidays()
    
    # Add each holiday from the database to the holiday manager
    for holiday in holidays:
        date_str = holiday.date.strftime('%Y-%m-%d')
        holiday_manager.add_holiday(date_str, description=holiday.description)
    
    flash('Database holiday state synchronized successfully')
    return redirect(url_for('holidays.index'))

@holidays_bp.route('/add-range', methods=['GET', 'POST'])
@login_required
def add_range():
    form = HolidayRangeForm()
    if form.validate_on_submit():
        start_date = form.start_date.data
        end_date = form.end_date.data
        description = form.description.data
        
        # Get existing holidays to avoid duplicates
        existing_holidays = set(h.date for h in Holiday.query.all())
        
        # Calculate the date range
        current_date = start_date
        days_added = 0
        weekends_skipped = 0
        existing_skipped = 0
        
        while current_date <= end_date:
            # Skip weekends (0 = Monday, 6 = Sunday in isoweekday)
            if current_date.isoweekday() in [6, 7]:  # Saturday and Sunday
                weekends_skipped += 1
                current_date += timedelta(days=1)
                continue
                
            # Skip existing holidays
            if current_date in existing_holidays:
                existing_skipped += 1
                current_date += timedelta(days=1)
                continue
                
            # Add new holiday
            holiday = Holiday(date=current_date, description=description)
            db.session.add(holiday)
            days_added += 1
            current_date += timedelta(days=1)
        
        if days_added > 0:
            db.session.commit()
            
            # Sync the holiday manager - but don't clear existing holidays
            holiday_manager = HolidayManager()
            
            # Only add the newly added holidays to the manager
            for date in [h.date for h in Holiday.query.filter(Holiday.date >= start_date, Holiday.date <= end_date).all()]:
                date_str = date.strftime('%Y-%m-%d')
                holiday_manager.add_holiday(date_str, description=description)
                
            flash(f'Successfully added {days_added} holidays. Skipped {weekends_skipped} weekend days and {existing_skipped} existing holidays.', 'success')
            return redirect(url_for('holidays.index'))
        else:
            flash('No holidays were added. All dates in the range were either weekends or already holidays.', 'warning')
    
    return render_template('holidays/add_range.html', form=form, title='Add Holiday Range') 
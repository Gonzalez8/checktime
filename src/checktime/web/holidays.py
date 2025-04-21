from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired
from datetime import datetime

from checktime.web.models import db, Holiday
from checktime.fichaje.holidays import HolidayManager

holidays_bp = Blueprint('holidays', __name__, url_prefix='/holidays')

class HolidayForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Save')

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
            flash('Holiday already exists for this date')
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
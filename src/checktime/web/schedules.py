from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, BooleanField, SubmitField, SelectField, TimeField, FormField, FieldList
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, date

from checktime.web.models import db, SchedulePeriod, DaySchedule

schedules_bp = Blueprint('schedules', __name__, url_prefix='/schedules')

class DayScheduleForm(FlaskForm):
    day_of_week = SelectField('Day', choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), 
                                             (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), 
                                             (6, 'Sunday')], coerce=int)
    check_in_time = StringField('Check-in Time (HH:MM)', validators=[DataRequired()])
    check_out_time = StringField('Check-out Time (HH:MM)', validators=[DataRequired()])

class SchedulePeriodForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')
    
    def validate_end_date(self, field):
        if field.data < self.start_date.data:
            raise ValidationError('End date must be after start date')

@schedules_bp.route('/')
@login_required
def index():
    """List all schedule periods."""
    periods = SchedulePeriod.query.order_by(SchedulePeriod.start_date).all()
    return render_template('schedules/index.html', title='Schedule Periods', periods=periods)

@schedules_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new schedule period."""
    form = SchedulePeriodForm()
    if form.validate_on_submit():
        # Check for overlapping periods
        overlapping = SchedulePeriod.query.filter(
            SchedulePeriod.start_date <= form.end_date.data,
            SchedulePeriod.end_date >= form.start_date.data
        ).first()
        
        if overlapping and form.is_active.data:
            flash('This period overlaps with another period. Please adjust the dates.')
            return redirect(url_for('schedules.add'))
        
        period = SchedulePeriod(
            name=form.name.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            is_active=form.is_active.data
        )
        db.session.add(period)
        db.session.commit()
        
        flash('Schedule period added successfully')
        return redirect(url_for('schedules.edit_days', period_id=period.id))
    
    return render_template('schedules/add.html', title='Add Schedule Period', form=form)

@schedules_bp.route('/edit/<int:period_id>', methods=['GET', 'POST'])
@login_required
def edit(period_id):
    """Edit an existing schedule period."""
    period = SchedulePeriod.query.get_or_404(period_id)
    form = SchedulePeriodForm(obj=period)
    
    if form.validate_on_submit():
        # Check for overlapping periods
        overlapping = SchedulePeriod.query.filter(
            SchedulePeriod.id != period_id,
            SchedulePeriod.start_date <= form.end_date.data,
            SchedulePeriod.end_date >= form.start_date.data
        ).first()
        
        if overlapping and form.is_active.data:
            flash('This period overlaps with another period. Please adjust the dates.')
            return redirect(url_for('schedules.edit', period_id=period_id))
        
        period.name = form.name.data
        period.start_date = form.start_date.data
        period.end_date = form.end_date.data
        period.is_active = form.is_active.data
        
        db.session.commit()
        flash('Schedule period updated successfully')
        return redirect(url_for('schedules.index'))
    
    return render_template('schedules/edit.html', title='Edit Schedule Period', form=form, period=period)

@schedules_bp.route('/delete/<int:period_id>', methods=['POST'])
@login_required
def delete(period_id):
    """Delete a schedule period."""
    period = SchedulePeriod.query.get_or_404(period_id)
    db.session.delete(period)
    db.session.commit()
    
    flash('Schedule period deleted successfully')
    return redirect(url_for('schedules.index'))

@schedules_bp.route('/period/<int:period_id>/days', methods=['GET', 'POST'])
@login_required
def edit_days(period_id):
    """Edit the daily schedules for a period."""
    period = SchedulePeriod.query.get_or_404(period_id)
    
    if request.method == 'POST':
        # Clear existing day schedules
        for schedule in period.schedules:
            db.session.delete(schedule)
        
        # Add new day schedules from form data
        for day in range(7):  # 0-6 for Monday-Sunday
            if f'day_{day}_enabled' in request.form:
                check_in = request.form.get(f'day_{day}_check_in', '')
                check_out = request.form.get(f'day_{day}_check_out', '')
                
                if check_in and check_out:
                    schedule = DaySchedule(
                        period_id=period_id,
                        day_of_week=day,
                        check_in_time=check_in,
                        check_out_time=check_out
                    )
                    db.session.add(schedule)
        
        db.session.commit()
        flash('Daily schedules updated successfully')
        return redirect(url_for('schedules.index'))
    
    # Prepare existing schedules for template
    day_schedules = {schedule.day_of_week: schedule for schedule in period.schedules}
    
    return render_template(
        'schedules/edit_days.html',
        title='Edit Day Schedules',
        period=period,
        day_schedules=day_schedules,
        days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    ) 
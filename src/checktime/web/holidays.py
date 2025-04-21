from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, timedelta
import os
import tempfile

# Importación segura de icalendar
try:
    from icalendar import Calendar
    HAS_ICALENDAR = True
except ImportError:
    HAS_ICALENDAR = False

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

class ICalendarImportForm(FlaskForm):
    ics_file = FileField('ICS File', validators=[
        FileRequired(),
        FileAllowed(['ics'], 'Only ICS files are allowed!')
    ])
    submit = SubmitField('Import Holidays')

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

@holidays_bp.route('/import-ics', methods=['GET', 'POST'])
@login_required
def import_ics():
    """Import holidays from an ICS file."""
    # Verificar si la biblioteca icalendar está disponible
    if not HAS_ICALENDAR:
        flash('The icalendar library is not installed. Please install it to use this feature.', 'danger')
        return redirect(url_for('holidays.index'))
    
    form = ICalendarImportForm()
    
    if form.validate_on_submit():
        try:
            # Save the uploaded file to a temporary location
            ics_file = form.ics_file.data
            fd, temp_path = tempfile.mkstemp(suffix='.ics')
            
            try:
                # Write the file content to the temporary file
                with os.fdopen(fd, 'wb') as tmp:
                    tmp.write(ics_file.read())
                
                # Parse the ICS file
                with open(temp_path, 'rb') as f:
                    cal = Calendar.from_ical(f.read())
                
                # Process events
                events_added = 0
                duplicates = 0
                
                for component in cal.walk():
                    if component.name == "VEVENT":
                        event_date = component.get('dtstart').dt
                        
                        # If event_date is a datetime (not just a date), convert to date
                        if isinstance(event_date, datetime):
                            event_date = event_date.date()
                        
                        # Get event summary/description
                        summary = component.get('summary', 'Imported Holiday')
                        
                        # Check if holiday already exists
                        existing = Holiday.query.filter_by(date=event_date).first()
                        if existing:
                            duplicates += 1
                            continue
                        
                        # Add to database
                        holiday = Holiday(date=event_date, description=str(summary))
                        db.session.add(holiday)
                        events_added += 1
                
                if events_added > 0:
                    db.session.commit()
                    
                    # Sync with holiday manager
                    holiday_manager = HolidayManager()
                    
                    # Get all holidays from the database
                    holidays = Holiday.query.all()
                    for holiday in holidays:
                        date_str = holiday.date.strftime('%Y-%m-%d')
                        holiday_manager.add_holiday(date_str, description=holiday.description)
                    
                    flash(f'Successfully imported {events_added} holidays. {duplicates} duplicates were skipped.', 'success')
                    return redirect(url_for('holidays.index'))
                else:
                    flash(f'No holidays were imported. {duplicates} duplicates were found.', 'warning')
                    
            except Exception as e:
                flash(f'Error importing ICS file: {str(e)}', 'danger')
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as outer_e:
            flash(f'Error processing the file: {str(outer_e)}', 'danger')
    
    return render_template('holidays/import_ics.html', form=form, title='Import Holidays from ICS') 
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, g
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, timedelta
import os
import tempfile
import logging

# Importación segura de icalendar
try:
    from icalendar import Calendar
    HAS_ICALENDAR = True
except ImportError:
    HAS_ICALENDAR = False

from checktime.shared.models.holiday import Holiday
from checktime.shared.repository import holiday_repository
from checktime.shared.services.holiday_manager import HolidayManager
from checktime.web.translations import get_translation

holidays_bp = Blueprint('holidays', __name__, url_prefix='/holidays')

def get_language():
    """Get the current language from session or default to 'en'"""
    return session.get('lang', 'en')

class HolidayForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Save')
    
    def __init__(self, *args, **kwargs):
        super(HolidayForm, self).__init__(*args, **kwargs)
        # Set translated labels
        lang = get_language()
        self.date.label.text = get_translation('date', lang)
        self.description.label.text = get_translation('description', lang)
        self.submit.label.text = get_translation('btn_save_holiday', lang)

class HolidayRangeForm(FlaskForm):
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Add Range')
    
    def __init__(self, *args, **kwargs):
        super(HolidayRangeForm, self).__init__(*args, **kwargs)
        # Set translated labels
        lang = get_language()
        self.start_date.label.text = get_translation('start_date', lang)
        self.end_date.label.text = get_translation('end_date', lang)
        self.description.label.text = get_translation('description', lang)
        self.submit.label.text = get_translation('btn_add_range', lang)
    
    def validate_end_date(self, field):
        if field.data < self.start_date.data:
            lang = get_language()
            raise ValidationError(get_translation('end_date_after_start', lang))

# Import from iCalendar if the library is available
try:
    from icalendar import Calendar
    
    class ICalendarImportForm(FlaskForm):
        ics_file = FileField('ICS File', validators=[
            FileRequired(),
            FileAllowed(['ics'], 'Only ICS files are allowed!')
        ])
        submit = SubmitField('Import Holidays')
        
        def __init__(self, *args, **kwargs):
            super(ICalendarImportForm, self).__init__(*args, **kwargs)
            # Set translated labels
            lang = get_language()
            self.ics_file.label.text = get_translation('ics_file', lang)
            self.submit.label.text = get_translation('btn_import_holidays', lang)
    
    ICALENDAR_AVAILABLE = True
except ImportError:
    ICALENDAR_AVAILABLE = False
    logging.warning("icalendar library not available. ICS import disabled.")

def flash_message(key, category='success'):
    """Flash a message with proper translation based on current language context"""
    # Get language from Flask g object if available, otherwise from session
    lang = getattr(g, 'language', get_language())
    flash(get_translation(key, lang), category)

@holidays_bp.route('/')
@login_required
def index():
    """List all holidays."""
    holidays = holiday_repository.get_all()
    return render_template('holidays/index.html', title='Holidays', holidays=holidays, icalendar_available=ICALENDAR_AVAILABLE)

@holidays_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new holiday."""
    form = HolidayForm()
    if form.validate_on_submit():
        # Check if holiday already exists
        existing = holiday_repository.get_by_date(form.date.data)
        if existing:
            flash_message('holiday_already_exists', 'danger')
            return redirect(url_for('holidays.index'))
        
        # Add to database
        holiday_repository.create(form.date.data, form.description.data)
        flash_message('holiday_added')
        return redirect(url_for('holidays.index'))
    
    return render_template('holidays/add.html', title='Add Holiday', form=form)

@holidays_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Edit an existing holiday."""
    holiday = holiday_repository.get_by_id(id)
    if not holiday:
        flash_message('holiday_not_found', 'danger')
        return redirect(url_for('holidays.index'))
        
    form = HolidayForm(obj=holiday)
    # Update the submit button label to reflect an update operation
    lang = get_language()
    form.submit.label.text = get_translation('btn_update_holiday', lang)
    
    if form.validate_on_submit():
        holiday_repository.update(holiday, date=form.date.data, description=form.description.data)
        flash_message('holiday_updated')
        return redirect(url_for('holidays.index'))
    
    return render_template('holidays/edit.html', title='Edit Holiday', form=form, holiday=holiday)

@holidays_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete a holiday."""
    holiday = holiday_repository.get_by_id(id)
    if not holiday:
        flash_message('holiday_not_found', 'danger')
        return redirect(url_for('holidays.index'))
        
    holiday_repository.delete(holiday)
    flash_message('holiday_deleted')
    return redirect(url_for('holidays.index'))

@holidays_bp.route('/sync')
@login_required
def sync():
    """Update holidays in memory with current database state."""
    # Create a holiday manager instance
    holiday_manager = HolidayManager()
    
    # Get all holidays from the database
    holidays = holiday_repository.get_all()
    
    # Clear existing holidays and add each one from the database
    holiday_manager.clear_holidays()
    
    # Add each holiday from the database to the holiday manager
    for holiday in holidays:
        date_str = holiday.date.strftime('%Y-%m-%d')
        holiday_manager.add_holiday(date_str, description=holiday.description)
    
    flash_message('holidays_synced')
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
        all_holidays = holiday_repository.get_all()
        existing_holidays = set(h.date for h in all_holidays)
        
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
            holiday_repository.create(current_date, description)
            days_added += 1
            current_date += timedelta(days=1)
        
        if days_added > 0:
            # Get language for custom message construction
            lang = getattr(g, 'language', get_language())
            flash(f"{get_translation('holidays_added_success', lang)} {days_added} {get_translation('holidays', lang).lower()}. {get_translation('skipped', lang)} {weekends_skipped} {get_translation('weekends', lang).lower()} {get_translation('and', lang)} {existing_skipped} {get_translation('existing_holidays', lang).lower()}", 'success')
            return redirect(url_for('holidays.index'))
        else:
            flash_message('no_holidays_added', 'warning')
    
    return render_template('holidays/add_range.html', form=form, title='Add Holiday Range')

@holidays_bp.route('/import-ics', methods=['GET', 'POST'])
@login_required
def import_ics():
    """Import holidays from an ICS file."""
    # Verificar si la biblioteca icalendar está disponible
    if not HAS_ICALENDAR:
        flash_message('icalendar_not_installed', 'danger')
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
                        lang = getattr(g, 'language', get_language())
                        summary = component.get('summary', get_translation('imported_holiday', lang))
                        
                        # Check if holiday already exists
                        existing = holiday_repository.get_by_date(event_date)
                        if existing:
                            duplicates += 1
                            continue
                        
                        # Add to database
                        holiday_repository.create(event_date, str(summary))
                        events_added += 1
                
                if events_added > 0:
                    flash(f"{get_translation('import_success', lang)} {events_added} {get_translation('holidays', lang).lower()}. {duplicates} {get_translation('duplicates_skipped', lang)}", 'success')
                    return redirect(url_for('holidays.index'))
                else:
                    lang = getattr(g, 'language', get_language())
                    flash(f"{get_translation('no_holidays_imported', lang)} {duplicates} {get_translation('duplicates_found', lang)}", 'warning')
                    
            except Exception as e:
                lang = getattr(g, 'language', get_language())
                flash(f"{get_translation('error_importing_ics', lang)}: {str(e)}", 'danger')
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as outer_e:
            lang = getattr(g, 'language', get_language())
            flash(f"{get_translation('error_processing_file', lang)}: {str(outer_e)}", 'danger')
    
    return render_template('holidays/import_ics.html', form=form, title='Import Holidays from ICS')

if ICALENDAR_AVAILABLE:
    @holidays_bp.route('/import_ical', methods=['GET', 'POST'])
    @login_required
    def import_ical():
        """Import holidays from an iCalendar file."""
        form = ICalendarImportForm()
        if form.validate_on_submit():
            try:
                file_data = request.files['ics_file'].read()
                cal = Calendar.from_ical(file_data)
                
                added_count = 0
                skipped_count = 0
                
                holiday_manager = HolidayManager()
                
                for component in cal.walk():
                    if component.name == "VEVENT":
                        event_date = component.get('dtstart').dt
                        
                        # Skip if not a date (e.g. datetime)
                        if not isinstance(event_date, datetime.date):
                            continue
                        
                        summary = str(component.get('summary', 'Imported Holiday'))
                        
                        # Check if holiday already exists
                        existing = holiday_repository.get_by_date(event_date)
                        if existing:
                            skipped_count += 1
                        else:
                            # Create new holiday
                            holiday_repository.create(event_date, summary)
                            
                            # Add to holiday file
                            try:
                                date_str = event_date.strftime('%Y-%m-%d')
                                holiday_manager.add_holiday(date_str)
                                added_count += 1
                            except Exception as e:
                                logging.error(f"Error adding holiday {date_str} to file: {str(e)}")
                
                # Commit all changes
                holiday_repository.commit()
                
                # Flash message with results
                lang = get_language()
                if added_count > 0:
                    flash(get_translation('holidays_imported', lang).format(count=added_count))
                if skipped_count > 0:
                    flash(get_translation('holidays_skipped', lang).format(count=skipped_count), 'warning')
                    
                return redirect(url_for('holidays.index'))
            except Exception as e:
                logging.error(f"Error importing iCalendar: {str(e)}")
                lang = get_language()
                flash(get_translation('error_importing', lang), 'error')
        
        return render_template('holidays/import_ical.html', form=form) 
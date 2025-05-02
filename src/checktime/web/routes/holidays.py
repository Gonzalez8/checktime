from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, g, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, timedelta
import os
import tempfile
import logging
import json

# Importación segura de icalendar
try:
    from icalendar import Calendar
    HAS_ICALENDAR = True
except ImportError:
    HAS_ICALENDAR = False

from checktime.shared.models.holiday import Holiday
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
    lang = getattr(g, 'language', get_language())
    flash(get_translation(key, lang), category)

@holidays_bp.route('/')
@login_required
def index():
    """List all holidays."""
    holiday_manager = HolidayManager(current_user.id)
    holidays = holiday_manager.get_all_holidays()
    return render_template('holidays/index.html', title='Holidays', holidays=holidays, icalendar_available=ICALENDAR_AVAILABLE)

@holidays_bp.route('/sync')
@login_required
def sync():
    """Update holidays in memory with current database state."""
    # Create a holiday manager instance
    holiday_manager = HolidayManager(current_user.id)
    
    # Trigger a reload of holidays
    holiday_manager.reload_holidays()
    
    flash_message('holidays_synced')
    return redirect(url_for('holidays.index'))

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
                
                # Import the ICS file using the holiday manager
                holiday_manager = HolidayManager(current_user.id)
                result = holiday_manager.import_ics_file(temp_path)
                
                # Show results
                lang = getattr(g, 'language', get_language())
                if result['added'] > 0:
                    flash(f"{get_translation('import_success', lang)} {result['added']} {get_translation('holidays', lang).lower()}. {result['skipped']} {get_translation('duplicates_skipped', lang)}", 'success')
                    return redirect(url_for('holidays.index'))
                else:
                    flash(f"{get_translation('no_holidays_imported', lang)} {result['skipped']} {get_translation('duplicates_found', lang)}", 'warning')
                    
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
                
                # Use the holiday manager to import from file data
                holiday_manager = HolidayManager(current_user.id)
                result = holiday_manager.import_ics_data(file_data)
                
                # Flash message with results
                lang = get_language()
                if result['added'] > 0:
                    flash(get_translation('holidays_imported', lang).format(count=result['added']))
                if result['skipped'] > 0:
                    flash(get_translation('holidays_skipped', lang).format(count=result['skipped']), 'warning')
                    
                return redirect(url_for('holidays.index'))
            except Exception as e:
                logging.error(f"Error importing iCalendar: {str(e)}")
                lang = get_language()
                flash(get_translation('error_importing', lang), 'error')
        
        return render_template('holidays/import_ical.html', form=form) 

@holidays_bp.route('/dates')
@login_required
def get_dates():
    """Get all holiday dates as JSON for calendar integration."""
    try:
        holiday_manager = HolidayManager(current_user.id)
        dates = holiday_manager.get_all_dates()
        return jsonify(dates)
    except Exception as e:
        logging.error(f"Error fetching holiday dates: {str(e)}")
        return jsonify([]), 500 

@holidays_bp.route('/api/add', methods=['POST'])
@login_required
def api_add():
    """API endpoint for adding a single holiday."""
    try:
        data = request.get_json()
        
        if not data or 'date' not in data or 'description' not in data:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        holiday_manager = HolidayManager(current_user.id)
        
        # Parse date if it's a string
        date_value = data['date']
        if isinstance(date_value, str):
            try:
                date_obj = datetime.strptime(date_value, '%Y-%m-%d').date()
                # Keep the string version for add_holiday
                date_str = date_value
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid date format'}), 400
        else:
            # If it's already a date object, convert to string for the add_holiday method
            date_obj = date_value
            date_str = date_obj.strftime('%Y-%m-%d')
        
        # Add holiday
        success = holiday_manager.add_holiday(
            date=date_str,
            description=data['description'],
            user_id=current_user.id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': get_translation('holiday_added', get_language()),
                'holiday': {
                    'date': date_str,
                    'description': data['description']
                }
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': get_translation('holiday_already_exists', get_language())
            }), 409
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@holidays_bp.route('/api/add-range', methods=['POST'])
@login_required
def api_add_range():
    """API endpoint for adding a range of holidays."""
    try:
        data = request.get_json()
        
        if not data or 'start_date' not in data or 'end_date' not in data or 'description' not in data:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        # Parse dates if they're strings
        start_date = data['start_date']
        end_date = data['end_date']
        
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid start date format'}), 400
                
        if isinstance(end_date, str):
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid end date format'}), 400
        
        # Validate end date is after start date
        if end_date < start_date:
            return jsonify({
                'success': False, 
                'message': get_translation('end_date_after_start', get_language())
            }), 400
        
        holiday_manager = HolidayManager(current_user.id)
        
        # Add range of holidays
        result = holiday_manager.add_holiday_range(
            start_date=start_date,
            end_date=end_date,
            description=data['description'],
            skip_weekends=True
        )
        
        if result['added'] > 0:
            lang = get_language()
            message = f"{get_translation('holidays_added_success', lang)} {result['added']} {get_translation('holidays', lang).lower()}. {get_translation('skipped', lang)} {result['weekends_skipped']} {get_translation('weekends', lang).lower()} {get_translation('and', lang)} {result['existing_skipped']} {get_translation('existing_holidays', lang).lower()}"
            
            return jsonify({
                'success': True,
                'message': message,
                'result': result
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': get_translation('no_holidays_added', get_language())
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500 

@holidays_bp.route('/api/edit', methods=['POST'])
@login_required
def api_edit():
    """API endpoint for editing a holiday."""
    try:
        data = request.get_json()
        
        if not data or 'id' not in data or 'date' not in data or 'description' not in data:
            return jsonify({'success': False, 'message': get_translation('missing_required_fields', get_language())}), 400
            
        holiday_manager = HolidayManager(current_user.id)
        
        # Ensure holiday_id is an integer
        try:
            holiday_id = int(data['id'])
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': get_translation('invalid_id_format', get_language())}), 400
        
        # Parse date if it's a string
        date_value = data['date']
        if isinstance(date_value, str):
            try:
                date_obj = datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': get_translation('invalid_date_format', get_language())}), 400
        else:
            date_obj = date_value
        
        # Update holiday
        success = holiday_manager.update_holiday(
            holiday_id=holiday_id,
            date=date_obj,
            description=data['description']
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': get_translation('holiday_updated', get_language()),
                'holiday': {
                    'id': holiday_id,
                    'date': date_obj.strftime('%Y-%m-%d') if hasattr(date_obj, 'strftime') else date_obj,
                    'description': data['description']
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': get_translation('holiday_already_exists', get_language())
            }), 409
    except Exception as e:
        logging.error(f"Error editing holiday: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@holidays_bp.route('/api/delete', methods=['POST'])
@login_required
def api_delete():
    """Delete a holiday via AJAX."""
    try:
        data = request.get_json()
        
        if not data or 'id' not in data:
            return jsonify({
                'success': False,
                'message': get_translation('invalid_request', get_language())
            }), 400
        
        holiday_id = data['id']
        
        # Get the holiday manager
        holiday_manager = HolidayManager(current_user.id)
        
        # Delete the holiday
        success = holiday_manager.delete_holiday_by_id(holiday_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': get_translation('holiday_deleted', get_language())
            })
        else:
            return jsonify({
                'success': False,
                'message': get_translation('holiday_not_found', get_language())
            }), 404
            
    except Exception as e:
        logging.error(f"Error deleting holiday: {str(e)}")
        return jsonify({
            'success': False,
            'message': get_translation('error_deleting_holiday', get_language())
        }), 500

@holidays_bp.route('/api/update', methods=['PUT'])
@login_required
def api_update_by_date():
    """Update a holiday by date via AJAX."""
    try:
        data = request.get_json()
        
        if not data or 'date' not in data or 'description' not in data:
            return jsonify({
                'success': False,
                'message': get_translation('invalid_request', get_language())
            }), 400
        
        date_str = data['date']
        description = data['description']
        
        try:
            # Parse the date
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': get_translation('invalid_date_format', get_language())
            }), 400
        
        # Get the holiday manager
        holiday_manager = HolidayManager(current_user.id)
        
        # Check if a holiday with this date already exists
        holiday = holiday_manager.get_holiday_by_date(date)
        if not holiday:
            return jsonify({
                'success': False,
                'message': get_translation('holiday_not_found', get_language())
            }), 404
        
        # Update the holiday
        success = holiday_manager.update_holiday(
            holiday_id=holiday.id,
            date=date,
            description=description
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': get_translation('holiday_updated', get_language())
            })
        else:
            return jsonify({
                'success': False,
                'message': get_translation('error_updating_holiday', get_language())
            }), 500
            
    except Exception as e:
        logging.error(f"Error updating holiday: {str(e)}")
        return jsonify({
            'success': False,
            'message': get_translation('error_updating_holiday', get_language())
        }), 500

@holidays_bp.route('/api/delete/<date>', methods=['DELETE'])
@login_required
def api_delete_by_date(date):
    """Delete a holiday by date via AJAX."""
    try:
        try:
            # Parse the date
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'message': get_translation('invalid_date_format', get_language())
            }), 400
        
        # Get the holiday manager
        holiday_manager = HolidayManager(current_user.id)
        
        # Get holiday by date
        holiday = holiday_manager.get_holiday_by_date(parsed_date)
        if not holiday:
            return jsonify({
                'success': False,
                'message': get_translation('holiday_not_found', get_language())
            }), 404
        
        # Delete the holiday
        success = holiday_manager.delete_holiday_by_id(holiday.id)
        
        if success:
            return jsonify({
                'success': True,
                'message': get_translation('holiday_deleted', get_language())
            })
        else:
            return jsonify({
                'success': False,
                'message': get_translation('error_deleting_holiday', get_language())
            }), 500
            
    except Exception as e:
        logging.error(f"Error deleting holiday: {str(e)}")
        return jsonify({
            'success': False,
            'message': get_translation('error_deleting_holiday', get_language())
        }), 500 

@holidays_bp.route('/partial')
@login_required
def partial():
    """Return partial HTML for holiday list to support AJAX updates."""
    holiday_manager = HolidayManager(current_user.id)
    holidays = holiday_manager.get_all_holidays()
    return render_template('holidays/partials/holiday_list.html', holidays=holidays) 
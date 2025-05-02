"""
API routes for managing day overrides.
"""

from datetime import datetime
from flask import Blueprint, jsonify, request, flash, g
from flask_login import login_required, current_user

from checktime.shared.services.day_override_manager import DayOverrideManager
from checktime.web.translations import get_translation

bp = Blueprint('overrides', __name__, url_prefix='/api/overrides')

def flash_message(key, category='success'):
    """Flash a message with proper translation based on current language context"""
    lang = getattr(g, 'language', get_language())
    flash(get_translation(key, lang), category)

def get_language():
    """Get the current language from session or default to 'en'"""
    from flask import session
    return session.get('lang', 'en')

@bp.route('', methods=['POST'])
@login_required
def create_override():
    """Create a new day override."""
    try:
        data = request.get_json()
        
        date_str = data.get('date')
        check_in_time = data.get('check_in_time')
        check_out_time = data.get('check_out_time')
        description = data.get('description')
        
        if not all([date_str, check_in_time, check_out_time]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
        # Parse date
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Create override
        manager = DayOverrideManager(current_user.id)
        override = manager.create_override(
            target_date=target_date,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            description=description
        )
        
        if override:
            return jsonify({
                'success': True,
                'override': {
                    'id': override.id,
                    'date': override.date.strftime('%Y-%m-%d'),
                    'check_in_time': override.check_in_time,
                    'check_out_time': override.check_out_time,
                    'description': override.description
                }
            }), 201
        else:
            return jsonify({'success': False, 'message': 'Override already exists for this date'}), 409
    except ValueError as e:
        flash(str(e), 'danger')
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        flash(get_translation('error_saving_override', get_language()), 'danger')
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@bp.route('/<date>', methods=['GET'])
@login_required
def get_override(date):
    """Get a day override by date."""
    try:
        # Parse date
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get override
        manager = DayOverrideManager(current_user.id)
        override = manager.get_override_for_date(target_date)
        
        if override:
            return jsonify({
                'success': True,
                'override': {
                    'id': override.id,
                    'date': override.date.strftime('%Y-%m-%d'),
                    'check_in_time': override.check_in_time,
                    'check_out_time': override.check_out_time,
                    'description': override.description
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Override not found'}), 404
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@bp.route('/<date>', methods=['PUT'])
@login_required
def update_override(date):
    """Update a day override."""
    try:
        # Parse date
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        data = request.get_json()
        check_in_time = data.get('check_in_time')
        check_out_time = data.get('check_out_time')
        description = data.get('description')
        
        if not all([check_in_time, check_out_time]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Update override
        manager = DayOverrideManager(current_user.id)
        override = manager.update_override(
            target_date=target_date,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            description=description
        )
        
        if override:
            return jsonify({
                'success': True,
                'override': {
                    'id': override.id,
                    'date': override.date.strftime('%Y-%m-%d'),
                    'check_in_time': override.check_in_time,
                    'check_out_time': override.check_out_time,
                    'description': override.description
                }
            })
        else:
            # Add error flash message
            flash(get_translation('override_not_found', get_language()), 'danger')
            return jsonify({'success': False, 'message': 'Override not found'}), 404
    except ValueError as e:
        flash(str(e), 'danger')
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        flash(get_translation('error_saving_override', get_language()), 'danger')
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@bp.route('/<date>', methods=['DELETE'])
@login_required
def delete_override(date):
    """Delete a day override."""
    try:
        # Parse date
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Delete override
        manager = DayOverrideManager(current_user.id)
        if manager.delete_override(target_date):
            return jsonify({'success': True}), 204
        else:
            # Add error flash message
            flash(get_translation('override_not_found', get_language()), 'danger')
            return jsonify({'success': False, 'message': 'Override not found'}), 404
    except ValueError as e:
        flash(str(e), 'danger')
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        flash(get_translation('error_deleting_override', get_language()), 'danger')
        return jsonify({'success': False, 'message': 'Internal server error'}), 500 
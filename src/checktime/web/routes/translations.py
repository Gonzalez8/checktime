from flask import Blueprint, jsonify, session, g
from checktime.web.translations import get_translation, TRANSLATIONS

translations_bp = Blueprint('translations', __name__, url_prefix='/api/translations')

def get_current_language():
    """Get the current user language from session or g"""
    return getattr(g, 'language', session.get('language', 'en'))

@translations_bp.route('/')
def get_all_translations():
    """Return all translations for the current language"""
    lang = get_current_language()
    return jsonify(TRANSLATIONS.get(lang, TRANSLATIONS['en']))

@translations_bp.route('/<lang>')
def get_translations_for_language(lang):
    """Return all translations for a specific language"""
    if lang not in TRANSLATIONS:
        lang = 'en'  # Default to English for unknown languages
    return jsonify(TRANSLATIONS[lang])

@translations_bp.route('/keys/<keys>')
def get_translation_keys(keys):
    """Return translations for specific keys"""
    lang = get_current_language()
    keys_list = keys.split(',')
    translations = {}
    
    for key in keys_list:
        translations[key] = get_translation(key, lang)
        
    return jsonify(translations)

@translations_bp.route('/group/<group>')
def get_translation_group(group):
    """Return translations for a specific group (holidays, dashboard, etc.)"""
    lang = get_current_language()
    
    # Define groups of related translation keys
    groups = {
        'holidays': [
            'field_required', 
            'holiday_already_exists', 
            'error_saving_holiday', 
            'error_updating_holiday', 
            'error_deleting_holiday', 
            'end_date_after_start',
            'holiday_added',
            'holiday_updated',
            'holiday_deleted',
            'invalid_date_format',
            'add_holiday',
            'edit_holiday',
            'delete_holiday',
            'date',
            'description',
            'confirm_delete_holiday'
        ],
        'dashboard': [
            'error_loading_calendar',
            'error_saving_override',
            'error_deleting_override',
            'confirm_delete_override',
            'create_override',
            'edit_override',
            'loading',
            'calendar_will_load_here',
            'select_day_type',
            'override_deleted',
            'override_updated',
            'override_created',
            'error_missing_date',
            'error_missing_id',
            'error_creating_override',
            'error_updating_override',
        ],
        'schedules': [
            'schedule_periods',
            'manage_schedules',
            'add_period',
            'edit_period',
            'delete_period',
            'name',
            'start_date',
            'end_date',
            'status',
            'active',
            'inactive',
            'actions',
            'confirm_delete',
            'confirm_delete_period',
            'delete_period_warning',
            'cancel',
            'delete',
            'period_not_found',
            'period_updated',
            'period_added',
            'schedule_period_deleted',
            'period_name',
            'active_period',
            'end_date_after_start',
            'period_overlap_error',
            'monday',
            'tuesday',
            'wednesday',
            'thursday',
            'friday',
            'saturday',
            'sunday',
            'edit_day_schedules',
            'quick_actions',
            'configure_daily_schedules',
            'daily_check_times',
            'day_schedules',
            'schedule_templates',
            'back',
            'save',
            'standard_schedule',
            'summer_schedule',
            'flexible_schedule',
            'check_in_time',
            'check_out_time',
            'day_schedules_updated'
        ],
        'common': [
            'cancel',
            'save',
            'delete',
            'edit',
            'add',
            'create'
        ]
    }
    
    # Get the keys for the requested group
    keys_list = groups.get(group, [])
    if not keys_list:
        return jsonify({})
    
    translations = {}
    for key in keys_list:
        translations[key] = get_translation(key, lang)
    
    return jsonify(translations) 
import logging
import os
from flask import Flask, request, session, redirect, url_for, g, render_template
from flask_login import LoginManager, current_user
from sqlalchemy import text

from checktime.shared.db import db, init_db
from checktime.shared.config import get_secret_key, get_database_url
from checktime.shared.models.user import User
from checktime.shared.models.captcha import PendingCaptcha  # noqa: F401 - register table
from checktime.shared.services.user_manager import UserManager
from checktime.web.translations import t

logger = logging.getLogger(__name__)


def _apply_lightweight_migrations(app):
    """Add columns that newer code expects but older databases may lack.

    Why: the project relies on db.create_all() which never adds columns to
    existing tables. Postgres' ADD COLUMN IF NOT EXISTS makes this safe to
    run on every boot without a real migration tool.
    """
    statements = [
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(128)",
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS password_reset_token_expires_at TIMESTAMP",
        # Widen pending_captcha.response from 8 chars (v1.8.0) to 32 (v1.8.1)
        # since the user now sends 10 keypad digits + 6 captcha digits.
        "ALTER TABLE pending_captcha ALTER COLUMN response TYPE VARCHAR(32)",
        # v1.9.0: optional per-user Gemini API key for automatic captcha
        # solving (encrypted at rest via checktime.utils.crypto).
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS google_api_key VARCHAR(512)",
    ]
    with app.app_context():
        with db.engine.begin() as conn:
            for stmt in statements:
                try:
                    conn.execute(text(stmt))
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Skipping migration %r: %s", stmt, exc)

login_manager = LoginManager()

def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder='static',
        static_url_path='/static'
    )
    
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=get_secret_key(),
        SQLALCHEMY_DATABASE_URI=get_database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Babel configuration
        LANGUAGES = ['en', 'es'],
        BABEL_DEFAULT_LOCALE = 'en',
    )
    
    # Override with test config if passed
    if test_config:
        app.config.update(test_config)
    
    # Initialize extensions
    init_db(app)
    login_manager.init_app(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    _apply_lightweight_migrations(app)
    
    # Register blueprints
    from checktime.web.routes.auth import auth_bp
    from checktime.web.routes.dashboard import dashboard_bp
    from checktime.web.routes.holidays import holidays_bp
    from checktime.web.routes.schedules import schedules_bp
    from checktime.web.routes.overrides import bp as overrides_bp
    from checktime.web.routes.translations import translations_bp
    from checktime.web.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(holidays_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(overrides_bp)
    app.register_blueprint(translations_bp)
    app.register_blueprint(admin_bp)
    
    @login_manager.user_loader
    def load_user(user_id):
        # Use UserManager to load the user
        user_manager = UserManager()
        return user_manager.get_by_id(int(user_id))
    
    # Configure login view
    login_manager.login_view = 'auth.login'
    
    # Root route for homepage
    @app.route('/')
    def home():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('home.html')
    
    # Language selector route
    @app.route('/language/<lang_code>')
    def set_language(lang_code):
        # Store language preference in session
        session['language'] = lang_code if lang_code in app.config['LANGUAGES'] else app.config['BABEL_DEFAULT_LOCALE']
        # Redirect back to the previous page or home
        return redirect(request.referrer or url_for('home'))
    
    @app.before_request
    def before_request():
        # Set locale based on user preference
        language = session.get('language')
        if language:
            # We'll use session for now instead of Flask-Babel
            # This will be used in templates to display the right content
            g.language = language
        else:
            g.language = app.config['BABEL_DEFAULT_LOCALE']
    
    # Add template context processor for translations
    @app.context_processor
    def inject_translations():
        def translate(key, default=None):
            # Use the language from the flask g object (set in before_request)
            translation = t(key, g.language)
            # If translation is the same as key and a default is provided, use default
            if translation == key and default is not None:
                return default
            return translation
        
        # Make translate function and languages available in all templates
        return dict(
            _=translate,  # shortcut function for translation
            languages=app.config['LANGUAGES'],
            current_language=g.get('language', app.config['BABEL_DEFAULT_LOCALE'])
        )
            
    return app 
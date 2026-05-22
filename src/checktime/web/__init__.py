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

    Strategy: each operation runs in its OWN transaction (so one failure
    doesn't poison the rest), and column additions are guarded by an
    information_schema check (so we can log clearly which columns we
    actually had to add). The double belt-and-braces of
    "ADD COLUMN IF NOT EXISTS" plus an explicit existence check is
    deliberate — earlier versions hit a case where IF NOT EXISTS
    silently failed inside an aborted transaction.
    """
    # (table, column, type) for every column the current code expects
    # that older deployments may not have.
    columns_to_ensure = [
        ('"user"', 'password_reset_token_hash', 'VARCHAR(128)'),
        ('"user"', 'password_reset_token_expires_at', 'TIMESTAMP'),
        ('"user"', 'google_api_key', 'VARCHAR(512)'),
        ('"user"', 'gemini_model', 'VARCHAR(64)'),
    ]
    # Type-change statements that aren't safe to retry blindly — they
    # only matter on older schemas.
    type_changes = [
        ('pending_captcha', 'response', 'VARCHAR(32)'),
    ]

    with app.app_context():
        # Log the current user table schema so we can diagnose mismatches.
        try:
            with db.engine.begin() as conn:
                rows = conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'user' ORDER BY ordinal_position"
                )).fetchall()
                logger.info(
                    "Existing user table columns: %s",
                    [r[0] for r in rows] or "(none)",
                )
        except Exception as exc:
            logger.warning("Could not introspect user table: %s", exc)

        for table, column, type_def in columns_to_ensure:
            try:
                with db.engine.begin() as conn:
                    exists = conn.execute(
                        text(
                            "SELECT 1 FROM information_schema.columns "
                            "WHERE table_name = :t AND column_name = :c"
                        ),
                        {"t": table.strip('"'), "c": column},
                    ).fetchone()
                    if exists:
                        continue
                    conn.execute(
                        text(f'ALTER TABLE {table} ADD COLUMN {column} {type_def}')
                    )
                    logger.info("Migration: added %s.%s %s", table, column, type_def)
            except Exception as exc:
                logger.warning(
                    "Migration failed for %s.%s: %s", table, column, exc,
                )

        for table, column, new_type in type_changes:
            try:
                with db.engine.begin() as conn:
                    # Only widen if the existing column is narrower than expected.
                    row = conn.execute(
                        text(
                            "SELECT character_maximum_length "
                            "FROM information_schema.columns "
                            "WHERE table_name = :t AND column_name = :c"
                        ),
                        {"t": table, "c": column},
                    ).fetchone()
                    if row is None:
                        # Column doesn't exist yet (table itself missing or
                        # column missing). create_all() handles fresh tables.
                        continue
                    # Extract numeric size from "VARCHAR(N)"
                    import re as _re
                    m = _re.search(r"\((\d+)\)", new_type)
                    target = int(m.group(1)) if m else None
                    current = row[0]
                    if target is None or current is None or current >= target:
                        continue
                    conn.execute(
                        text(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_type}')
                    )
                    logger.info(
                        "Migration: widened %s.%s from %s to %s",
                        table, column, current, target,
                    )
            except Exception as exc:
                logger.warning(
                    "Type change failed for %s.%s: %s", table, column, exc,
                )

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
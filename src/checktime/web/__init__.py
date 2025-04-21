import os
from flask import Flask, request, session, redirect, url_for, g
from flask_login import LoginManager
from checktime.web.models import db, User
from checktime.web.translations import t

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
        SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:////data/checktime.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Babel configuration
        LANGUAGES = ['en', 'es'],
        BABEL_DEFAULT_LOCALE = 'en',
    )
    
    # Override with test config if passed
    if test_config:
        app.config.update(test_config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        
        # Create admin user if it doesn't exist
        if User.query.filter_by(username='admin').first() is None:
            admin = User(username='admin', email='admin@example.com', is_admin=True)
            admin.set_password(os.getenv('ADMIN_PASSWORD', 'admin'))
            db.session.add(admin)
            db.session.commit()
    
    # Register blueprints
    from checktime.web.auth import auth_bp
    from checktime.web.dashboard import dashboard_bp
    from checktime.web.holidays import holidays_bp
    from checktime.web.schedules import schedules_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(holidays_bp)
    app.register_blueprint(schedules_bp)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Configure login view
    login_manager.login_view = 'auth.login'
    
    # Language selector route
    @app.route('/language/<lang_code>')
    def set_language(lang_code):
        # Store language preference in session
        session['language'] = lang_code if lang_code in app.config['LANGUAGES'] else app.config['BABEL_DEFAULT_LOCALE']
        # Redirect back to the previous page or home
        return redirect(request.referrer or url_for('dashboard.index'))
    
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
        def translate(key):
            # Use the language from the flask g object (set in before_request)
            return t(key, g.language)
        
        # Make translate function and languages available in all templates
        return dict(
            _=translate,  # shortcut function for translation
            languages=app.config['LANGUAGES'],
            current_language=g.get('language', app.config['BABEL_DEFAULT_LOCALE'])
        )
            
    return app 
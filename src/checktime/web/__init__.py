import os
from flask import Flask
from flask_login import LoginManager
from checktime.web.models import db, User

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
    
    return app 
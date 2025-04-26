from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional

from checktime.shared.models.user import User
from checktime.shared.repository import user_repository
from checktime.shared.config import get_admin_password
from checktime.web.translations import get_translation

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def get_language():
    """Get the current language from session or default to 'en'"""
    return session.get('lang', 'en')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    # CheckJC credentials (optional during registration)
    checkjc_username = StringField('CheckJC Username', validators=[Optional()])
    checkjc_password = PasswordField('CheckJC Password', validators=[Optional()])
    auto_checkin_enabled = BooleanField('Enable Auto Check-in/out', default=True)
    # Telegram settings (optional during registration)
    telegram_chat_id = StringField('Telegram Chat ID', validators=[Optional()])
    telegram_notifications_enabled = BooleanField('Enable Telegram Notifications', default=True)
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = user_repository.get_by_username(username.data)
        if user is not None:
            lang = get_language()
            raise ValidationError(get_translation('username_taken', lang))
    
    def validate_email(self, email):
        user = user_repository.get_by_email(email.data)
        if user is not None:
            lang = get_language()
            raise ValidationError(get_translation('email_taken', lang))

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional()])
    confirm_password = PasswordField('Confirm New Password', validators=[EqualTo('new_password')])
    submit = SubmitField('Update Profile')
    
    def __init__(self, original_username, original_email, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email
    
    def validate_username(self, username):
        if username.data != self.original_username:
            user = user_repository.get_by_username(username.data)
            if user is not None:
                lang = get_language()
                raise ValidationError(get_translation('username_taken', lang))
    
    def validate_email(self, email):
        if email.data != self.original_email:
            user = user_repository.get_by_email(email.data)
            if user is not None:
                lang = get_language()
                raise ValidationError(get_translation('email_taken', lang))

class CheckJCCredentialsForm(FlaskForm):
    checkjc_username = StringField('CheckJC Username', validators=[Optional()])
    checkjc_password = PasswordField('CheckJC Password', validators=[Optional()])
    auto_checkin_enabled = BooleanField('Enable Auto Check-in/out', default=True)
    submit = SubmitField('Save CheckJC Credentials')

class TelegramSettingsForm(FlaskForm):
    telegram_chat_id = StringField('Telegram Chat ID', validators=[Optional()])
    telegram_notifications_enabled = BooleanField('Enable Telegram Notifications', default=True)
    submit = SubmitField('Save Telegram Settings')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = user_repository.get_by_username(form.username.data)
        if user is None or not user.check_password(form.password.data):
            flash(get_translation('invalid_username_or_password', get_language()), 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard.index')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Create user
        user = user_repository.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        
        # Set CheckJC credentials if provided
        if form.checkjc_username.data and form.checkjc_password.data:
            user_repository.set_checkjc_credentials(
                user_id=user.id,
                username=form.checkjc_username.data,
                password=form.checkjc_password.data,
                enabled=form.auto_checkin_enabled.data
            )
            
        # Set Telegram settings if provided
        if form.telegram_chat_id.data:
            user_repository.set_telegram_settings(
                user_id=user.id,
                chat_id=form.telegram_chat_id.data,
                enabled=form.telegram_notifications_enabled.data
            )
            
        flash(get_translation('account_created', get_language()), 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form) 

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(current_user.username, current_user.email)
    
    if form.validate_on_submit():
        # Check current password if the user is trying to change their password
        if form.new_password.data and not current_user.check_password(form.current_password.data):
            flash(get_translation('invalid_password', get_language()), 'danger')
            return redirect(url_for('auth.profile'))
        
        # Update user information
        user_repository.update_user(
            user=current_user,
            username=form.username.data,
            email=form.email.data,
            password=form.new_password.data if form.new_password.data else None
        )
        
        flash(get_translation('profile_updated', get_language()), 'success')
        return redirect(url_for('auth.profile'))
    
    # Pre-fill form with current values
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    
    checkjc_form = CheckJCCredentialsForm()
    telegram_form = TelegramSettingsForm()
    
    # Handle CheckJC form submission
    if checkjc_form.is_submitted() and 'checkjc_submit' in request.form:
        user_repository.set_checkjc_credentials(
            user_id=current_user.id,
            username=checkjc_form.checkjc_username.data,
            password=checkjc_form.checkjc_password.data if checkjc_form.checkjc_password.data else current_user.checkjc_password,
            enabled=checkjc_form.auto_checkin_enabled.data
        )
        flash(get_translation('checkjc_credentials_updated', get_language()), 'success')
        return redirect(url_for('auth.profile') + '#checkjc-config')
    
    # Handle Telegram form submission
    if telegram_form.is_submitted() and 'telegram_submit' in request.form:
        user_repository.set_telegram_settings(
            user_id=current_user.id,
            chat_id=telegram_form.telegram_chat_id.data,
            enabled=telegram_form.telegram_notifications_enabled.data
        )
        flash(get_translation('telegram_settings_updated', get_language()), 'success')
        return redirect(url_for('auth.profile') + '#telegram-config')
    
    # Pre-fill CheckJC form with current values
    if request.method == 'GET':
        checkjc_form.checkjc_username.data = current_user.checkjc_username
        checkjc_form.auto_checkin_enabled.data = current_user.auto_checkin_enabled
        
        # Pre-fill Telegram form with current values
        telegram_form.telegram_chat_id.data = current_user.telegram_chat_id
        telegram_form.telegram_notifications_enabled.data = current_user.telegram_notifications_enabled
    
    return render_template('auth/profile.html', title='Profile', form=form, 
                          checkjc_form=checkjc_form, telegram_form=telegram_form) 
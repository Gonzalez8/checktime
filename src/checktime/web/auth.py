from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError

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
        user_repository.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        flash(get_translation('account_created', get_language()), 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form) 
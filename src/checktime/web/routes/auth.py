import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Optional, Length

from checktime.scheduler.captcha_solver import LLMVisionSolver
from checktime.shared.services.user_manager import UserManager
from checktime.utils.telegram import TelegramClient
from checktime.web.translations import get_translation

logger = logging.getLogger(__name__)

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
    checkjc_subdomain = StringField('CheckJC Subdomain', validators=[DataRequired()])
    auto_checkin_enabled = BooleanField('Enable Auto Check-in/out', default=True)
    # Telegram settings (optional during registration)
    telegram_chat_id = StringField('Telegram Chat ID', validators=[Optional()])
    telegram_notifications_enabled = BooleanField('Enable Telegram Notifications', default=True)
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user_manager = UserManager()
        user = user_manager.get_by_username(username.data)
        if user is not None:
            lang = get_language()
            raise ValidationError(get_translation('username_taken', lang))
    
    def validate_email(self, email):
        user_manager = UserManager()
        user = user_manager.get_by_email(email.data)
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
            user_manager = UserManager()
            user = user_manager.get_by_username(username.data)
            if user is not None:
                lang = get_language()
                raise ValidationError(get_translation('username_taken', lang))
    
    def validate_email(self, email):
        if email.data != self.original_email:
            user_manager = UserManager()
            user = user_manager.get_by_email(email.data)
            if user is not None:
                lang = get_language()
                raise ValidationError(get_translation('email_taken', lang))

class CheckJCCredentialsForm(FlaskForm):
    checkjc_username = StringField('CheckJC Username', validators=[Optional()])
    checkjc_password = PasswordField('CheckJC Password', validators=[Optional()])
    checkjc_subdomain = StringField('CheckJC Subdomain', validators=[DataRequired()])
    auto_checkin_enabled = BooleanField('Enable Auto Check-in/out', default=True)
    submit = SubmitField('Save CheckJC Credentials')

class TelegramSettingsForm(FlaskForm):
    telegram_chat_id = StringField('Telegram Chat ID', validators=[Optional()])
    telegram_notifications_enabled = BooleanField('Enable Telegram Notifications', default=True)
    submit = SubmitField('Save Telegram Settings')

class GoogleApiKeyForm(FlaskForm):
    google_api_key = PasswordField('Google API Key', validators=[Optional()])
    gemini_model = SelectField(
        'Gemini Model',
        choices=[(m, m) for m in LLMVisionSolver.SUPPORTED_MODELS],
        default=LLMVisionSolver.DEFAULT_MODEL,
        validators=[Optional()],
    )
    submit = SubmitField('Save Google API Key')

class ForgotPasswordForm(FlaskForm):
    identifier = StringField('Username or Email', validators=[DataRequired()])
    submit = SubmitField('Send reset link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    password2 = PasswordField('Repeat New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset password')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user_manager = UserManager()
        user = user_manager.get_by_username(form.username.data)
        if user is None or not user.check_password(form.password.data):
            flash(get_translation('invalid_username_or_password', get_language()), 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard.index')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = ForgotPasswordForm()
    lang = get_language()
    if form.validate_on_submit():
        user_manager = UserManager()
        user, raw_token = user_manager.create_password_reset_token(form.identifier.data)

        delivered_via_telegram = False
        if user and raw_token and user.telegram_chat_id:
            reset_url = url_for('auth.reset_password', token=raw_token, _external=True)
            message = (
                f"🔐 *CheckTime*\n\n"
                f"{get_translation('reset_telegram_intro', lang)}\n\n"
                f"[{get_translation('reset_telegram_link', lang)}]({reset_url})\n\n"
                f"_{get_translation('reset_telegram_expiry', lang)}_"
            )
            try:
                delivered_via_telegram = TelegramClient().send_message(
                    message,
                    chat_id=user.telegram_chat_id,
                    parse_mode="Markdown",
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Error sending password reset Telegram message: %s", exc)
                delivered_via_telegram = False

        if user and not delivered_via_telegram:
            logger.info(
                "Password reset requested for user %s but Telegram delivery was not possible",
                user.username,
            )

        # Always show the same response to avoid leaking which accounts exist
        # or which ones have Telegram configured.
        flash(get_translation('reset_request_received', lang), 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html',
                           title=get_translation('forgot_password', lang),
                           form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    lang = get_language()
    user_manager = UserManager()
    user = user_manager.verify_password_reset_token(token)
    if user is None:
        flash(get_translation('reset_token_invalid', lang), 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        updated = user_manager.reset_password_with_token(token, form.password.data)
        if updated is None:
            flash(get_translation('reset_token_invalid', lang), 'danger')
            return redirect(url_for('auth.forgot_password'))
        flash(get_translation('reset_password_success', lang), 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html',
                           title=get_translation('reset_password', lang),
                           form=form, username=user.username)


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
        user_manager = UserManager()
        # Create user
        user = user_manager.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        
        # Set CheckJC credentials if provided
        if form.checkjc_username.data and form.checkjc_password.data and form.checkjc_subdomain.data:
            user_manager.set_checkjc_credentials(
                user_id=user.id,
                username=form.checkjc_username.data,
                password=form.checkjc_password.data,
                enabled=form.auto_checkin_enabled.data,
                subdomain=form.checkjc_subdomain.data
            )
        else:
            # Guardar el subdominio aunque no haya usuario/contraseña
            user.checkjc_subdomain = form.checkjc_subdomain.data
            user_manager.repository.update(user)
        
        # Set Telegram settings if provided
        if form.telegram_chat_id.data:
            user_manager.set_telegram_settings(
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
    user_manager = UserManager()
    
    if form.validate_on_submit():
        # Check current password if the user is trying to change their password
        if form.new_password.data and not current_user.check_password(form.current_password.data):
            flash(get_translation('invalid_password', get_language()), 'danger')
            return redirect(url_for('auth.profile'))
        
        # Update user information
        user_manager.update_user(
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
    google_api_form = GoogleApiKeyForm()
    
    # Handle CheckJC form submission
    if checkjc_form.is_submitted() and 'checkjc_submit' in request.form:
        user_manager.set_checkjc_credentials(
            user_id=current_user.id,
            username=checkjc_form.checkjc_username.data,
            password=checkjc_form.checkjc_password.data if checkjc_form.checkjc_password.data else current_user.checkjc_password,
            enabled=checkjc_form.auto_checkin_enabled.data,
            subdomain=checkjc_form.checkjc_subdomain.data
        )
        flash(get_translation('checkjc_credentials_updated', get_language()), 'success')
        return redirect(url_for('auth.profile') + '#checkjc-config')
    
    # Handle Telegram form submission
    if telegram_form.is_submitted() and 'telegram_submit' in request.form:
        user_manager.set_telegram_settings(
            user_id=current_user.id,
            chat_id=telegram_form.telegram_chat_id.data,
            enabled=telegram_form.telegram_notifications_enabled.data
        )
        flash(get_translation('telegram_settings_updated', get_language()), 'success')
        return redirect(url_for('auth.profile') + '#telegram-config')

    # Handle Google API key form submission
    if google_api_form.is_submitted() and 'google_api_submit' in request.form:
        if 'google_api_clear' in request.form:
            user_manager.set_google_api_key(current_user.id, None)
            flash(get_translation('google_api_key_cleared', get_language()), 'success')
        else:
            # Always persist the model selection (cheap, idempotent).
            selected_model = (google_api_form.gemini_model.data or "").strip()
            if selected_model in LLMVisionSolver.SUPPORTED_MODELS:
                user_manager.set_gemini_model(current_user.id, selected_model)

            new_key = (google_api_form.google_api_key.data or "").strip()
            if new_key:
                user_manager.set_google_api_key(current_user.id, new_key)
                flash(get_translation('google_api_key_saved', get_language()), 'success')
            else:
                # Empty key field: just updated the model preference.
                flash(get_translation('google_api_key_unchanged', get_language()), 'info')
        return redirect(url_for('auth.profile') + '#google-api-config')

    # Pre-fill CheckJC form with current values
    if request.method == 'GET':
        checkjc_form.checkjc_username.data = current_user.checkjc_username
        checkjc_form.auto_checkin_enabled.data = current_user.auto_checkin_enabled
        checkjc_form.checkjc_subdomain.data = current_user.checkjc_subdomain

        # Pre-fill Telegram form with current values
        telegram_form.telegram_chat_id.data = current_user.telegram_chat_id
        telegram_form.telegram_notifications_enabled.data = current_user.telegram_notifications_enabled

        # Pre-select the Gemini model in the dropdown (NULL → default)
        google_api_form.gemini_model.data = (
            current_user.gemini_model or LLMVisionSolver.DEFAULT_MODEL
        )

    return render_template(
        'auth/profile.html',
        title='Profile',
        form=form,
        checkjc_form=checkjc_form,
        telegram_form=telegram_form,
        google_api_form=google_api_form,
        google_api_key_set=current_user.has_google_api_key(),
    )


@auth_bp.route('/profile/checkjc-password', methods=['GET'])
@login_required
def reveal_checkjc_password():
    """Return the decrypted CheckJC password of the currently authenticated
    user. Only ever exposes the caller's own password — there is no way
    to address another user's row.

    Used by the profile page so the operator can verify what's actually
    stored against what they expect, without retyping. The stored value
    is decrypted server-side and returned as JSON; the page already
    requires login, so the password is shown in the same trust boundary
    as the rest of the user's session data.
    """
    try:
        password = current_user.checkjc_password  # property already decrypts
    except Exception as exc:
        logger.exception("Failed to decrypt CheckJC password for user %s",
                         current_user.username)
        return jsonify({"error": "decrypt_failed", "detail": str(exc)}), 500
    return jsonify({"password": password or ""})

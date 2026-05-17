"""
Admin-only routes.

Includes the Telegram broadcast and basic user management (currently
limited to issuing one-time password resets for users who cannot
recover their account via Telegram).
"""

import logging
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from checktime.shared.services.user_manager import UserManager
from checktime.utils.telegram import TelegramClient
from checktime.web.translations import get_translation


logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _lang():
    return session.get('language', 'en')


def admin_required(view):
    """Decorator that lets only authenticated admins reach the view.

    Stacks AFTER login_required (Flask-Login handles the not-logged-in
    case). Anything else gets bounced to the dashboard with a flash.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            flash("Acceso restringido a administradores.", "danger")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)
    return wrapper


@admin_bp.route("/broadcast", methods=["GET", "POST"])
@login_required
@admin_required
def broadcast():
    user_manager = UserManager()
    candidates = user_manager.get_all_with_telegram_configured()

    if request.method == "GET":
        return render_template(
            "admin/broadcast.html",
            recipient_count=len(candidates),
            recipients=candidates,
        )

    message = (request.form.get("message") or "").strip()
    if not message:
        flash("El mensaje no puede estar vacío.", "warning")
        return redirect(url_for("admin.broadcast"))

    candidates_by_id = {user.id: user for user in candidates}

    selected_ids = []
    for raw in request.form.getlist("recipient_ids"):
        try:
            selected_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    targets = [candidates_by_id[uid] for uid in selected_ids if uid in candidates_by_id]
    if not targets:
        flash("Selecciona al menos un destinatario.", "warning")
        return redirect(url_for("admin.broadcast"))

    telegram = TelegramClient()
    sent = []
    failed = []
    for user in targets:
        ok = telegram.send_message(
            f"📢 *Aviso del administrador*\n\n{message}",
            chat_id=user.telegram_chat_id,
            parse_mode="Markdown",
        )
        (sent if ok else failed).append(user.username)

    logger.info(
        "Broadcast issued by %s to %d users: %d sent, %d failed",
        current_user.username, len(targets), len(sent), len(failed),
    )

    if failed:
        flash(
            f"Enviado a {len(sent)} usuarios. Falló para: {', '.join(failed)}.",
            "warning",
        )
    else:
        flash(f"Enviado a {len(sent)} usuarios.", "success")

    return redirect(url_for("admin.broadcast"))


@admin_bp.route("/users", methods=["GET"])
@login_required
@admin_required
def users():
    user_manager = UserManager()
    return render_template(
        "admin/users.html",
        users=user_manager.list_users(),
        temporary_password=None,
        target_user=None,
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user_manager = UserManager()
    target = user_manager.get_by_id(user_id)
    if target is None:
        abort(404)

    lang = _lang()
    if target.id == current_user.id:
        flash(get_translation("admin_delete_self_blocked", lang), "warning")
        return redirect(url_for("admin.users"))

    if target.is_admin and user_manager.count_admins() <= 1:
        flash(get_translation("admin_delete_last_admin_blocked", lang), "warning")
        return redirect(url_for("admin.users"))

    deleted_username = target.username
    if not user_manager.delete_user(user_id):
        flash(get_translation("admin_delete_failed", lang), "danger")
        return redirect(url_for("admin.users"))

    logger.info("Admin %s deleted user %s", current_user.username, deleted_username)
    flash(
        get_translation("admin_delete_success", lang).format(username=deleted_username),
        "success",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_user_password(user_id):
    user_manager = UserManager()
    target = user_manager.get_by_id(user_id)
    if target is None:
        abort(404)

    user, temporary_password = user_manager.admin_reset_password(user_id)
    if user is None or temporary_password is None:
        flash(get_translation("admin_reset_failed", _lang()), "danger")
        return redirect(url_for("admin.users"))

    logger.info(
        "Admin %s issued a temporary password for user %s",
        current_user.username, user.username,
    )

    # Render the same page so the temp password is shown inline once;
    # we deliberately avoid `flash` so it isn't persisted in the session.
    return render_template(
        "admin/users.html",
        users=user_manager.list_users(),
        temporary_password=temporary_password,
        target_user=user,
    )

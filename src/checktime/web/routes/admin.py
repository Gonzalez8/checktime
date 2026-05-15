"""
Admin-only routes.

For now only the Telegram broadcast lives here. Other admin features
can be added under the same blueprint.
"""

import logging
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from checktime.shared.services.user_manager import UserManager
from checktime.utils.telegram import TelegramClient


logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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
    recipients = user_manager.get_all_with_telegram_configured()

    if request.method == "GET":
        return render_template(
            "admin/broadcast.html",
            recipient_count=len(recipients),
            recipients=recipients,
        )

    message = (request.form.get("message") or "").strip()
    if not message:
        flash("El mensaje no puede estar vacío.", "warning")
        return redirect(url_for("admin.broadcast"))

    telegram = TelegramClient()
    sent = []
    failed = []
    for user in recipients:
        if not getattr(user, "telegram_chat_id", None):
            continue
        ok = telegram.send_message(
            f"📢 *Aviso del administrador*\n\n{message}",
            chat_id=user.telegram_chat_id,
            parse_mode="Markdown",
        )
        (sent if ok else failed).append(user.username)

    logger.info(
        "Broadcast issued by %s: %d sent, %d failed",
        current_user.username, len(sent), len(failed),
    )

    if failed:
        flash(
            f"Enviado a {len(sent)} usuarios. Falló para: {', '.join(failed)}.",
            "warning",
        )
    else:
        flash(f"Enviado a {len(sent)} usuarios.", "success")

    return redirect(url_for("admin.broadcast"))

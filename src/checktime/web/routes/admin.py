"""
Admin-only routes.

Includes the Telegram broadcast and basic user management (currently
limited to issuing one-time password resets for users who cannot
recover their account via Telegram).
"""

import logging
import os
import re
from functools import wraps

from flask import (
    Blueprint, abort, flash, redirect, render_template, request,
    send_file, session, url_for,
)
from flask_login import current_user, login_required

from checktime.shared.services.user_manager import UserManager
from checktime.utils.telegram import TelegramClient
from checktime.web.translations import get_translation


# Where the scheduler writes the per-user diagnostic dumps. Kept in sync
# with the paths used in checker.py and captcha_solver.py — change one,
# change both.
_CAPTCHA_DUMP_DIR = "/var/log/checktime/captcha_dumps"
_LOGIN_FAILURE_DIR = "/var/log/checktime/login_failures"

# Whitelist of category -> set of allowed extensions. Anything outside
# this map is rejected with a 404 in diagnostics_file().
_DIAG_CATEGORIES = {
    "captcha": {
        "dir": _CAPTCHA_DUMP_DIR,
        "exts": {"png", "txt"},
    },
    "login_failure": {
        "dir": _LOGIN_FAILURE_DIR,
        "exts": {"html", "png", "txt"},
    },
}


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


def _safe_username(raw):
    """Same sanitization the dumpers apply when they write the file."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", raw or "")


@admin_bp.route("/diagnostics")
@login_required
@admin_required
def diagnostics():
    """List all users with their available diagnostic dump artifacts.

    Reads the two on-disk directories (`captcha_dumps`, `login_failures`)
    and pairs whatever exists with the CheckTime users in the DB. Users
    with no dumps still appear so the operator knows the absence is
    real, not a miss.
    """
    user_manager = UserManager()
    rows = []
    for user in user_manager.list_users():
        # Captcha dumps are written by the solver using the CheckTime
        # app username (user.username). Login-failure dumps are written
        # by the checker using the CheckJC login (user.checkjc_username,
        # e.g. a DNI), which is what `self.username` resolves to there.
        # They are NOT the same string, so we must look each category up
        # under the name its own dumper used or the page shows "—" even
        # though the file exists on disk.
        safe = _safe_username(user.username)
        login_name = user.checkjc_username or user.username
        safe_login = _safe_username(login_name)
        cap_png = os.path.join(_CAPTCHA_DUMP_DIR, f"{safe}.png")
        cap_txt = os.path.join(_CAPTCHA_DUMP_DIR, f"{safe}.txt")
        log_png = os.path.join(_LOGIN_FAILURE_DIR, f"{safe_login}.png")
        log_txt = os.path.join(_LOGIN_FAILURE_DIR, f"{safe_login}.txt")
        log_html = os.path.join(_LOGIN_FAILURE_DIR, f"{safe_login}.html")

        def _mtime(path):
            try:
                return os.path.getmtime(path)
            except Exception:
                return None

        rows.append({
            "username": user.username,
            # Name the login-failure files are actually stored under, so
            # the template builds the download URL that resolves on disk.
            "login_username": login_name,
            "user_id": user.id,
            "captcha": {
                "png": os.path.exists(cap_png),
                "txt": os.path.exists(cap_txt),
                "mtime": _mtime(cap_png) or _mtime(cap_txt),
            },
            "login_failure": {
                "html": os.path.exists(log_html),
                "png": os.path.exists(log_png),
                "txt": os.path.exists(log_txt),
                "mtime": _mtime(log_png) or _mtime(log_html) or _mtime(log_txt),
            },
        })
    return render_template("admin/diagnostics.html", rows=rows)


@admin_bp.route("/diagnostics/file/<category>/<username>.<ext>")
@login_required
@admin_required
def diagnostics_file(category, username, ext):
    """Serve a single diagnostic dump file.

    Strict whitelisting:
    - category must be one of `_DIAG_CATEGORIES`
    - ext must be in the category's allowed set
    - username is regex-sanitized to the same set used by the dumpers,
      so no '..' / '/' / NUL bytes survive
    - file is only read from the category's fixed directory

    HTML is served as text/plain on purpose so any embedded scripts in
    the dumped CheckJC page do NOT execute under our origin. The
    operator can still read the markup.
    """
    spec = _DIAG_CATEGORIES.get(category)
    if not spec or ext not in spec["exts"]:
        abort(404)
    safe = _safe_username(username)
    if not safe:
        abort(404)
    path = os.path.join(spec["dir"], f"{safe}.{ext}")
    if not os.path.isfile(path):
        abort(404)
    mime = {
        "png": "image/png",
        "txt": "text/plain; charset=utf-8",
        # HTML on purpose served as plain so the dumped page can't run
        # scripts in our origin.
        "html": "text/plain; charset=utf-8",
    }[ext]
    return send_file(path, mimetype=mime, as_attachment=False, max_age=0)

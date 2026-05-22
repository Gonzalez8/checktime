"""
PendingCaptcha model: queue of captcha challenges awaiting human (or LLM) input.

The scheduler creates a row when CheckJC serves /verification after login.
The bot listener picks up the user's Telegram reply and writes the response
back. The scheduler polls the row until ANSWERED, EXPIRED, or FAILED.
"""

from datetime import datetime, timedelta

from checktime.shared.db import db, TimestampMixin

# State machine values for PendingCaptcha.state
STATE_WAITING = "WAITING"
STATE_ANSWERED = "ANSWERED"
STATE_EXPIRED = "EXPIRED"
STATE_CONSUMED = "CONSUMED"
STATE_FAILED = "FAILED"


class PendingCaptcha(db.Model, TimestampMixin):
    __tablename__ = "pending_captcha"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_type = db.Column(db.String(8), nullable=False)  # 'in' or 'out'
    state = db.Column(db.String(16), nullable=False, default=STATE_WAITING, index=True)
    captcha_image = db.Column(db.LargeBinary, nullable=True)
    response = db.Column(db.String(8), nullable=True)
    attempt = db.Column(db.Integer, nullable=False, default=1)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User", backref=db.backref("pending_captchas", cascade="all, delete-orphan"))

    @classmethod
    def create(cls, user_id: int, check_type: str, image_bytes: bytes,
               attempt: int = 1, ttl_seconds: int = 300) -> "PendingCaptcha":
        row = cls(
            user_id=user_id,
            check_type=check_type,
            captcha_image=image_bytes,
            attempt=attempt,
            expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
            state=STATE_WAITING,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

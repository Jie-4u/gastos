import os, csv, io, secrets, hashlib, math, re, smtplib, ssl, html, base64, json, hmac, time
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from urllib.parse import urlencode, urlsplit
from urllib.request import Request as URLRequest, urlopen
from urllib.error import HTTPError, URLError

def load_local_env():
    """Load simple KEY=VALUE entries without overriding host-provided env vars."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_file, encoding="utf-8-sig") as source:
            for raw in source:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name, value = name.strip(), value.strip()
                if value[:1] in ("'", '"') and value[-1:] == value[:1]:
                    value = value[1:-1]
                if name:
                    os.environ.setdefault(name, value)
    except FileNotFoundError:
        pass


load_local_env()

APP_TIMEZONE = timezone(timedelta(hours=8), "Asia/Manila")


def app_today():
    return datetime.now(APP_TIMEZONE).date()

app = Flask(__name__, static_folder="public", static_url_path="")
secret = os.environ.get("SECRET_KEY")
if not secret and os.environ.get("APP_ENV") == "production":
    raise RuntimeError("SECRET_KEY must be configured in production")
secret = secret or "local-development-only-change-me"
url = os.environ.get("DATABASE_URL", "sqlite:///gastos.db")
if url.startswith(("postgres://", "postgresql://")):
    # Name the installed driver: SQLAlchemy 2.1 otherwise defaults to psycopg 3, which isn't in requirements.txt.
    url = "postgresql+psycopg2://" + url.split("://", 1)[1]
def configured_app_base_url():
    return os.environ.get("APP_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")


if os.environ.get("APP_ENV") == "production":
    configured_base = configured_app_base_url()
    if not configured_base:
        raise RuntimeError("APP_BASE_URL or the hosting platform's public HTTPS URL must be configured in production")
    public_url = urlsplit(configured_base)
    if public_url.scheme != "https" or not public_url.netloc or public_url.username or public_url.password:
        raise RuntimeError("APP_BASE_URL must be a public HTTPS origin in production")
    if public_url.path not in ("", "/") or public_url.query or public_url.fragment:
        raise RuntimeError("APP_BASE_URL must be an origin without a path, query, or fragment")
    if url.startswith("sqlite:"):
        raise RuntimeError("DATABASE_URL must point to persistent PostgreSQL in production")
app.config.update(SQLALCHEMY_DATABASE_URI=url,
                  SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True})
db = SQLAlchemy(app)
ser = URLSafeTimedSerializer(secret)
invite_ser = URLSafeTimedSerializer(secret, salt="gastos-invitation-v1")
reset_ser = URLSafeTimedSerializer(secret, salt="gastos-password-reset-v1")
LIMIT = {"free": 4, "premium": 10}
FREE_BUDGETS = 3
MAX_WALLETS = 10  # per account
FAMILY_ROLES = ("Parent", "Member")


def can_manage_finances(user=None):
    user = user or g.u
    return bool(user.is_owner or user.role == "Parent")


class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    plan = db.Column(db.String(20), default="free")
    paymongo_customer_id = db.Column(db.String(100), unique=True)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    pw = db.Column(db.String(300), nullable=False)
    role = db.Column(db.String(40), default="Member")
    is_owner = db.Column(db.Boolean, default=False)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"))
    session_version = db.Column(db.Integer, nullable=False, default=0)
    reset_token_hash = db.Column(db.String(64))
    reset_requested_at = db.Column(db.DateTime)
    avatar_data = db.Column(db.Text)


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(200), nullable=False)
    token_hash = db.Column(db.String(64), unique=True)
    token_nonce = db.Column(db.String(64))
    role = db.Column(db.String(40), default="Member")
    inviter_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    accepted_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime)
    delivery_status = db.Column(db.String(24), nullable=False, default="manual_share")
    delivery_attempted_at = db.Column(db.DateTime)


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, nullable=False, index=True)
    plan = db.Column(db.String(20), nullable=False)
    period = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending_payment")
    provider_reference = db.Column(db.String(200), unique=True)
    payment_intent_id = db.Column(db.String(100), unique=True)
    payment_method = db.Column(db.String(24))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WebhookEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider_event_id = db.Column(db.String(120), unique=True, nullable=False)
    received_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Tx(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True)
    user_id = db.Column(db.Integer)
    kind = db.Column(db.String(10))  # income | expense
    amount = db.Column(db.Float)
    category = db.Column(db.String(60))
    note = db.Column(db.String(200), default="")
    date = db.Column(db.Date, default=app_today)
    status = db.Column(db.String(12), nullable=False, default="approved", server_default="approved")  # approved | pending | rejected
    receipt_data = db.Column(db.Text)
    wallet_id = db.Column(db.Integer, index=True)  # optional: which Cash/Card wallet this money moved through


class Wallet(db.Model):
    """A Cash Wallet or Card Wallet that belongs to one user account (private to that account).

    Its balance is opening_balance plus the approved transactions that account linked to it.

    For credit cards opening_balance is stored negative (money owed), so one formula covers every wallet.
    Only the last 4 digits of a card are stored: never the full number, expiry or CVV.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # cash | card
    name = db.Column(db.String(80), nullable=False)
    bank = db.Column(db.String(80))
    card_type = db.Column(db.String(10))  # debit | credit (cards only)
    last4 = db.Column(db.String(4))
    credit_limit = db.Column(db.Float)
    opening_balance = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(120))
    amount = db.Column(db.Float)
    due = db.Column(db.Date)
    paid = db.Column(db.Boolean, default=False)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(120))
    target = db.Column(db.Float)
    saved = db.Column(db.Float, default=0)


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True, nullable=False)
    category = db.Column(db.String(60), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)


def invitation_digest(inv):
    return hashlib.sha256(f"{inv.id}:{inv.token_nonce}".encode()).hexdigest()


with app.app_context():
    db.create_all()
    family_cols = {c["name"] for c in db.inspect(db.engine).get_columns("family")}
    for name, sql in {"paymongo_customer_id": "VARCHAR(100)"}.items():
        if name not in family_cols:
            with db.engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE family ADD COLUMN {name} {sql}")
    sub_cols = {c["name"] for c in db.inspect(db.engine).get_columns("subscription")}
    for name, sql in {"payment_intent_id": "VARCHAR(100)", "payment_method": "VARCHAR(24)"}.items():
        if name not in sub_cols:
            with db.engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE subscription ADD COLUMN {name} {sql}")
    user_cols = {c["name"] for c in db.inspect(db.engine).get_columns("user")}
    user_table = db.engine.dialect.identifier_preparer.quote(User.__tablename__)
    for name, sql in {"session_version": "INTEGER NOT NULL DEFAULT 0",
                      "reset_token_hash": "VARCHAR(64)", "reset_requested_at": "TIMESTAMP",
                      "avatar_data": "TEXT"}.items():
        if name not in user_cols:
            with db.engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE {user_table} ADD COLUMN {name} {sql}")
    tx_cols = {c["name"] for c in db.inspect(db.engine).get_columns("tx")}
    for name, sql in {"status": "VARCHAR(12) NOT NULL DEFAULT 'approved'", "receipt_data": "TEXT",
                      "wallet_id": "INTEGER"}.items():
        if name not in tx_cols:
            with db.engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE tx ADD COLUMN {name} {sql}")
    # Additive migration for databases created by earlier Gastos versions.
    cols ={c["name"] for c in db.inspect(db.engine).get_columns("invite")}
    for name, sql in {
        "token_hash": "VARCHAR(64)", "token_nonce": "VARCHAR(64)", "role": "VARCHAR(40) DEFAULT 'Member'",
        "inviter_id": "INTEGER", "created_at": "TIMESTAMP", "expires_at": "TIMESTAMP",
        "accepted_at": "TIMESTAMP", "revoked_at": "TIMESTAMP",
        "delivery_status": "VARCHAR(24) DEFAULT 'manual_share'", "delivery_attempted_at": "TIMESTAMP",
    }.items():
        if name not in cols:
            with db.engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE invite ADD COLUMN {name} {sql}")
    # Upgrade pending invitations from the earlier email-only schema to usable links.
    for inv in Invite.query.filter_by(token_nonce=None, accepted_at=None, revoked_at=None):
        inv.token_nonce = secrets.token_urlsafe(24)
        inv.expires_at = datetime.utcnow() + timedelta(days=7)
        signed = invite_ser.dumps({"id": inv.id, "nonce": inv.token_nonce})
        inv.token_hash = hashlib.sha256(signed.encode()).hexdigest()
    db.session.commit()


def err(m, c=400):
    return jsonify(error=m), c


def body():
    """The JSON request body, or {} when it is missing or not an object."""
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def premium():
    return g.f.plan == "premium"


def approved_tx():
    return Tx.query.filter_by(family_id=g.f.id, status="approved")


def image_data_url(value):
    """Validate a base64 image data URL; returns an error message or None."""
    match = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/]*={0,2})", value)
    if not match or len(value) > 1_400_000:
        return "Choose a JPEG, PNG, or WebP photo smaller than 1 MB"
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except (ValueError, base64.binascii.Error):
        return "The photo could not be read"
    mime = match.group(1)
    if not ((mime == "image/jpeg" and image_bytes.startswith(b"\xff\xd8\xff")) or
            (mime == "image/png" and image_bytes.startswith(b"\x89PNG\r\n\x1a\n")) or
            (mime == "image/webp" and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP")):
        return "The photo format is invalid"
    return None


@app.get("/health")
def health():
    """Lightweight readiness probe for production hosting platforms."""
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db.session.rollback()
        app.logger.exception("Health check database probe failed")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok"), 200


def auth(f):
    @wraps(f)
    def w(*a, **k):
        try:
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                raise BadSignature("missing bearer token")
            payload = ser.loads(header[7:], max_age=2592000)
        except (BadSignature, SignatureExpired):
            return err("Please sign in", 401)
        if isinstance(payload, dict) and type(payload.get("id")) is int:
            uid, version = payload["id"], payload.get("version")
        elif type(payload) is int:
            uid, version = payload, None  # legacy sessions remain valid until a password reset
        else:
            return err("Please sign in", 401)
        g.u = db.session.get(User, uid)
        if (not g.u or (version is None and g.u.session_version) or
                (version is not None and version != g.u.session_version)):
            return err("Please sign in", 401)
        return f(*a, **k)
    return w


def fam(f):
    @wraps(f)
    @auth
    def w(*a, **k):
        if not g.u.family_id:
            return err("Create a family first")
        g.f = db.session.get(Family, g.u.family_id)
        if not g.f:
            return err("Family not found", 404)
        return f(*a, **k)
    return w


def token(u):
    return ser.dumps({"id": u.id, "version": u.session_version or 0})


def public_app_link(params):
    base = configured_app_base_url()
    if not base:
        raise RuntimeError("APP_BASE_URL must be configured before sending invitations")
    parts = urlsplit(base)
    if (parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password
            or parts.query or parts.fragment):
        raise RuntimeError("APP_BASE_URL must be a valid public app origin without credentials, query, or fragment")
    if os.environ.get("APP_ENV") == "production" and parts.scheme != "https":
        raise RuntimeError("APP_BASE_URL must use HTTPS in production")
    return f"{base.rstrip('/')}/?{urlencode(params)}"


def invitation_link(inv):
    signed = invite_ser.dumps({"id": inv.id, "nonce": inv.token_nonce})
    return public_app_link({"invite": signed})


def invitation_from_token(value):
    try:
        data = invite_ser.loads(value)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("id"), int):
        return None
    inv = db.session.get(Invite, data.get("id"))
    digest = hashlib.sha256(value.encode()).hexdigest()
    return inv if inv and inv.token_hash and inv.token_nonce == data.get("nonce") and secrets.compare_digest(inv.token_hash, digest) else None


def send_invitation_email(inv, link):
    settings = (os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USERNAME"),
                os.environ.get("SMTP_PASSWORD"), os.environ.get("SMTP_FROM"))
    if not all(settings):
        return "manual_share"
    family = db.session.get(Family, inv.family_id)
    inviter = db.session.get(User, inv.inviter_id) if inv.inviter_id else None
    expires = inv.expires_at.strftime("%B %d, %Y %H:%M UTC") if inv.expires_at else "in 7 days"
    inviter_name = " ".join((inviter.name if inviter else "A Gastos family owner").split())[:120]
    family_name = " ".join((family.name if family else "your family").split())[:120]
    message = EmailMessage()
    message["Subject"] = f"You're invited to join {family_name} on Gastos"
    sender = os.environ["SMTP_FROM"]
    if "<" not in sender and "@" in sender:
        sender = formataddr((os.environ.get("SMTP_FROM_NAME", "Gastos"), sender))
    message["From"], message["To"] = sender, inv.email
    message.set_content(
        f"{inviter_name} invited you to join {family_name} on Gastos.\n\n"
        f"ACCEPT YOUR FAMILY INVITATION\n{link}\n\n"
        f"Gastos helps families manage household finances together. This invitation expires {expires}. "
        f"Sign in or create a Gastos account using {inv.email} to accept."
    )
    safe_name, safe_family = html.escape(inviter_name), html.escape(family_name)
    safe_email, safe_link, safe_expires = html.escape(inv.email), html.escape(link, quote=True), html.escape(expires)
    message.add_alternative(f"""<!doctype html>
<html lang="en"><body style="margin:0;background:#f4f7f5;font-family:Arial,sans-serif;color:#1b2430">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 12px;background:#f4f7f5"><tr><td align="center">
<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;width:100%;background:#fff;border:1px solid #e1e8e4;border-radius:16px">
<tr><td style="padding:28px 28px 8px;color:#167a55;font-size:24px;font-weight:bold">GASTOS</td></tr>
<tr><td style="padding:16px 28px 8px;font-size:22px;font-weight:bold">You’re invited to join {safe_family}</td></tr>
<tr><td style="padding:0 28px 22px;font-size:15px;line-height:1.6">{safe_name} invited you to manage household finances together on Gastos.</td></tr>
<tr><td align="center" style="padding:0 28px 12px"><a href="{safe_link}" style="display:inline-block;background:#167a55;color:#fff;text-decoration:none;padding:14px 22px;border-radius:8px;font-weight:bold">Accept Family Invitation</a></td></tr>
<tr><td style="padding:0 28px 20px;font-size:13px;line-height:1.6;color:#344054">Invitation link: <a href="{safe_link}" style="color:#167a55;overflow-wrap:anywhere">{safe_link}</a></td></tr>
<tr><td style="padding:0 28px 8px;font-size:13px;line-height:1.6;color:#667085">This invitation is for {safe_email} and expires {safe_expires}. Sign in or create an account with that email address to join.</td></tr>
<tr><td style="padding:0 28px 28px;font-size:12px;line-height:1.6;color:#667085">If the button doesn’t work, copy this link into your browser:<br><a href="{safe_link}" style="color:#167a55;overflow-wrap:anywhere">{safe_link}</a></td></tr>
</table></td></tr></table></body></html>""", subtype="html")
    try:
        host = os.environ["SMTP_HOST"]
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            server.send_message(message)
        return "sent"
    except (OSError, ValueError, smtplib.SMTPException) as exc:
        code = getattr(exc, "smtp_code", None) or getattr(exc, "errno", None)
        app.logger.error("Invitation email delivery failed (type=%s code=%s)", type(exc).__name__, code)
        return "failed"


def send_and_record_invitation(inv, link):
    status = send_invitation_email(inv, link)
    inv.delivery_status = status
    inv.delivery_attempted_at = datetime.utcnow() if status != "manual_share" else None
    db.session.commit()
    return status


def send_password_reset_email(user, link):
    settings = (os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USERNAME"),
                os.environ.get("SMTP_PASSWORD"), os.environ.get("SMTP_FROM"))
    if not all(settings):
        return "manual_share"
    message = EmailMessage()
    message["Subject"] = "Reset your Gastos password"
    sender = os.environ["SMTP_FROM"]
    if "<" not in sender and "@" in sender:
        sender = formataddr((os.environ.get("SMTP_FROM_NAME", "Gastos"), sender))
    message["From"], message["To"] = sender, user.email
    message.set_content(f"Use this link to reset your Gastos password. The link expires in 15 minutes.\n\n{link}\n\nIf you did not request a reset, you can ignore this email.")
    safe_link = html.escape(link, quote=True)
    message.add_alternative(f"""<!doctype html><html lang="en"><body style="margin:0;background:#f4f7f5;font-family:Arial,sans-serif;color:#1b2430"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 12px;background:#f4f7f5"><tr><td align="center"><table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;width:100%;background:#fff;border:1px solid #e1e8e4;border-radius:16px"><tr><td style="padding:28px;color:#167a55;font-size:24px;font-weight:bold">GASTOS</td></tr><tr><td style="padding:0 28px 12px;font-size:22px;font-weight:bold">Reset your password</td></tr><tr><td style="padding:0 28px 22px;font-size:15px;line-height:1.6">Use the secure button below to choose a new password. This link expires in 15 minutes.</td></tr><tr><td align="center" style="padding:0 28px 24px"><a href="{safe_link}" style="display:inline-block;background:#167a55;color:#fff;text-decoration:none;padding:14px 22px;border-radius:8px;font-weight:bold">Reset Password</a></td></tr><tr><td style="padding:0 28px 28px;font-size:12px;line-height:1.6;color:#667085">If you did not request this change, you can ignore this email.</td></tr></table></td></tr></table></body></html>""", subtype="html")
    try:
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587")), timeout=10) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            server.send_message(message)
        return "sent"
    except (OSError, ValueError, smtplib.SMTPException) as exc:
        code = getattr(exc, "smtp_code", None) or getattr(exc, "errno", None)
        app.logger.error("Password reset email failed (type=%s code=%s)", type(exc).__name__, code)
        return "failed"


class PayMongoError(Exception):
    def __init__(self, status=0):
        self.status = status


def paymongo_request(method, path, payload=None, idempotency_key=None):
    key = os.environ.get("PAYMENT_PROVIDER_SECRET", "")
    if not key or os.environ.get("PAYMENT_PROVIDER", "").lower() != "paymongo":
        raise PayMongoError()
    headers = {"Authorization": "Basic " + base64.b64encode((key + ":").encode()).decode(),
               "Accept": "application/json", "Content-Type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    body = json.dumps(payload).encode() if payload is not None else None
    req = URLRequest("https://api.paymongo.com/v1" + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            content = response.read()
            return json.loads(content) if content else {}
    except HTTPError as exc:
        raise PayMongoError(exc.code) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise PayMongoError() from None


def apply_subscription_status(subscription, provider_status):
    allowed = {"incomplete", "incomplete_cancelled", "active", "past_due", "unpaid", "cancelled"}
    if provider_status not in allowed:
        return False
    subscription.status = provider_status
    family = db.session.get(Family, subscription.family_id)
    if not family:
        return False
    if provider_status == "active":
        family.plan = "premium"
    elif provider_status in ("incomplete_cancelled", "unpaid", "cancelled"):
        other_active = Subscription.query.filter(
            Subscription.family_id == family.id,
            Subscription.status.in_(("active", "past_due")),
            Subscription.id != subscription.id,
        ).first()
        if not other_active:
            family.plan = "free"
    return True


@app.get("/")
def home():
    return send_from_directory("public", "index.html")


@app.post("/api/password-reset/request")
def password_reset_request():
    d = body()
    email = d.get("email") if isinstance(d.get("email"), str) else ""
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first() if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) else None
    now = datetime.utcnow()
    if user and (not user.reset_requested_at or user.reset_requested_at < now - timedelta(minutes=1)):
        try:
            reset_token = reset_ser.dumps({"id": user.id, "nonce": secrets.token_urlsafe(24)})
            user.reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
            user.reset_requested_at = now
            db.session.commit()
            link = public_app_link({"reset": reset_token})
            send_password_reset_email(user, link)
        except (RuntimeError, ValueError):
            db.session.rollback()
            app.logger.error("Password reset link could not be generated; check APP_BASE_URL")
        except Exception:
            db.session.rollback()
            app.logger.exception("Password reset request could not be completed")
    return jsonify(message="If an account exists for that email and email delivery is available, a password reset link will arrive shortly.")


@app.post("/api/password-reset/complete")
def password_reset_complete():
    d = body()
    value = d.get("token") if isinstance(d.get("token"), str) else ""
    password = d.get("password") if isinstance(d.get("password"), str) else ""
    if len(password) < 8:
        return err("Choose a password with at least 8 characters")
    try:
        payload = reset_ser.loads(value, max_age=900)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return err("This password reset link is invalid or expired", 400)
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
        return err("This password reset link is invalid or expired", 400)
    user = db.session.get(User, payload["id"])
    digest = hashlib.sha256(value.encode()).hexdigest()
    if (not user or not user.reset_token_hash or
            not secrets.compare_digest(user.reset_token_hash, digest) or
            not user.reset_requested_at or user.reset_requested_at < datetime.utcnow() - timedelta(minutes=15)):
        return err("This password reset link is invalid or expired", 400)
    user.pw = generate_password_hash(password)
    user.session_version = (user.session_version or 0) + 1
    user.reset_token_hash = None
    user.reset_requested_at = None
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/signup")
def signup():
    d = body()
    name = d.get("name") if isinstance(d.get("name"), str) else ""
    email = d.get("email") if isinstance(d.get("email"), str) else ""
    pw = d.get("password") if isinstance(d.get("password"), str) else ""
    name, email = name.strip(), email.strip().lower()
    if not name or len(name) > 120 or len(email) > 200 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(pw) < 8:
        return err("Enter a name, valid email and a password of 8+ characters")
    if User.query.filter_by(email=email).first():
        return err("Email already registered")
    invite_token = d.get("invite_token") if isinstance(d.get("invite_token"), str) else ""
    invited = None
    family = None
    if invite_token:
        invited = invitation_from_token(invite_token)
        if (not invited or invited.revoked_at or invited.accepted_at
                or (invited.expires_at and invited.expires_at <= datetime.utcnow())):
            return err("This invitation is invalid, expired, or no longer available", 404)
        if email != invited.email.lower():
            return err("Create the account using the email address this invitation was sent to", 403)
        family = db.session.get(Family, invited.family_id)
        used = User.query.filter_by(family_id=invited.family_id).count()
        if not family or used >= LIMIT.get(family.plan, LIMIT["free"]):
            return err("This family has reached its member limit", 409)
    u = User(name=name, email=email, pw=generate_password_hash(pw))
    if invited:
        u.family_id, u.role = invited.family_id, invited.role or "Member"
        invited.accepted_at = datetime.utcnow()
    db.session.add(u)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Account registration failed")
        return err("Could not complete registration. Please try again.", 500)
    return jsonify(token=token(u))


@app.post("/api/signin")
def signin():
    d = body()
    email = d.get("email") if isinstance(d.get("email"), str) else ""
    password = d.get("password") if isinstance(d.get("password"), str) else ""
    u = User.query.filter_by(email=email.strip().lower()).first()
    if not u or not check_password_hash(u.pw, password):
        return err("Wrong email or password", 401)
    return jsonify(token=token(u))


@app.get("/api/me")
@auth
def me():
    u, out = g.u, {"name": g.u.name, "email": g.u.email, "family": None}
    if u.family_id:
        f = db.session.get(Family, u.family_id)
        out["family"] = {"name": f.name, "plan": f.plan, "limit": LIMIT[f.plan], "owner": u.is_owner,
                         "role": "Owner" if u.is_owner else (u.role or "Member"),
                         "permissions": {"manage_members": bool(u.is_owner),
                                         "manage_finances": can_manage_finances(u),
                                         "manage_billing": bool(u.is_owner)},
                         "members": [{"id": m.id, "name": m.name, "role": m.role, "owner": m.is_owner}
                                     for m in User.query.filter_by(family_id=f.id)],
                         "invites": [{"id": i.id, "email": i.email, "role": i.role or "Member",
                                      "expires": i.expires_at.isoformat() if i.expires_at else None,
                                      "status": ("accepted" if i.accepted_at else "revoked" if i.revoked_at else
                                                 "expired" if i.expires_at and i.expires_at <= datetime.utcnow() else "pending"),
                                      "delivery": i.delivery_status or "manual_share",
                                      "link": invitation_link(i) if not i.accepted_at and not i.revoked_at and
                                              (not i.expires_at or i.expires_at > datetime.utcnow()) else None}
                                     for i in Invite.query.filter_by(family_id=f.id).order_by(Invite.id.desc()).limit(50)]}
    return jsonify(out)


@app.route("/api/profile", methods=["GET", "PUT"])
@auth
def profile():
    if request.method == "GET":
        return jsonify(name=g.u.name, email=g.u.email, avatar_data=g.u.avatar_data)

    data = body()
    name = data.get("name") if isinstance(data.get("name"), str) else g.u.name
    email = data.get("email") if isinstance(data.get("email"), str) else g.u.email
    name, email = name.strip(), email.strip().lower()
    if not name or len(name) > 120:
        return err("Enter a name with no more than 120 characters")
    if len(email) > 200 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return err("Enter a valid email address")
    if email != g.u.email.lower() and User.query.filter(User.email == email, User.id != g.u.id).first():
        return err("That email address is already registered", 409)

    new_password = data.get("new_password") if isinstance(data.get("new_password"), str) else ""
    current_password = data.get("current_password") if isinstance(data.get("current_password"), str) else ""
    credentials_change = email != g.u.email.lower() or bool(new_password)
    if credentials_change and not check_password_hash(g.u.pw, current_password):
        return err("Enter your current password to change your email or password", 403)
    if new_password and len(new_password) < 8:
        return err("Choose a new password with at least 8 characters")

    if "avatar_data" in data:
        avatar = data.get("avatar_data")
        if avatar == "":
            g.u.avatar_data = None
        elif isinstance(avatar, str):
            problem = image_data_url(avatar)
            if problem:
                return err(problem)
            g.u.avatar_data = avatar
        else:
            return err("The profile photo format is invalid")

    g.u.name, g.u.email = name, email
    password_changed = bool(new_password)
    if password_changed:
        g.u.pw = generate_password_hash(new_password)
        g.u.session_version = (g.u.session_version or 0) + 1
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Profile update failed")
        return err("Could not save profile changes. Please try again.", 500)
    result = {"ok": 1, "name": g.u.name, "email": g.u.email, "avatar_data": g.u.avatar_data}
    if password_changed:
        result["token"] = token(g.u)
    return jsonify(result)


@app.post("/api/family")
@auth
def make_family():
    d = body()
    if g.u.family_id:
        return err("You already have a family")
    name = d.get("name") if isinstance(d.get("name"), str) else ""
    if not name.strip():
        return err("Family name required")
    role = d.get("role", "Parent")
    if role not in ("Parent", "Member"):
        return err("Choose a supported family role")
    f = Family(name=name.strip()[:120], plan="free")
    db.session.add(f)
    db.session.flush()
    g.u.family_id, g.u.is_owner, g.u.role = f.id, True, role
    db.session.commit()
    return jsonify(ok=1)


@app.delete("/api/family/members/<int:user_id>")
@fam
def remove_family_member(user_id):
    if not g.u.is_owner:
        return err("Only the family owner can remove a member", 403)
    member = User.query.filter_by(id=user_id, family_id=g.f.id).first_or_404()
    if member.id == g.u.id or member.is_owner:
        return err("The family owner cannot be removed", 409)
    # Preserve the account and transaction history; only remove its family access.
    member.family_id = None
    member.role = "Member"
    member.is_owner = False
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Family member removal failed")
        return err("Could not remove this family member. Please try again.", 500)
    return jsonify(ok=1)


@app.put("/api/family/members/<int:user_id>/role")
@fam
def update_family_member_role(user_id):
    if not g.u.is_owner:
        return err("Only the family owner can change member roles", 403)
    member = User.query.filter_by(id=user_id, family_id=g.f.id).first_or_404()
    if member.is_owner:
        return err("The family owner's role cannot be changed", 409)
    role = body().get("role")
    if role not in FAMILY_ROLES:
        return err("Choose Parent or Member")
    member.role = role
    db.session.commit()
    return jsonify(ok=1, member={"id": member.id, "role": member.role})


@app.post("/api/invite")
@fam
def invite():
    if not g.u.is_owner:
        return err("Only the family owner can invite members", 403)
    data = body()
    raw_email = data.get("email", "")
    email = raw_email.strip().lower() if isinstance(raw_email, str) else ""
    if len(email) > 200 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return err("Enter a valid email")
    role = data.get("role", "Member")
    if role not in FAMILY_ROLES:
        return err("Choose Parent or Member")
    now = datetime.utcnow()
    used = User.query.filter_by(family_id=g.f.id).count() + Invite.query.filter_by(
        family_id=g.f.id, accepted_at=None, revoked_at=None
    ).filter(db.or_(Invite.expires_at.is_(None), Invite.expires_at > now)).count()
    if used >= LIMIT[g.f.plan]:
        return err(f"{g.f.plan.title()} plan allows up to {LIMIT[g.f.plan]} members. Upgrade for more.")
    u = User.query.filter_by(email=email).first()
    if u and u.family_id == g.f.id:
        return err("That person is already in this family")
    if u:
        return err("That person is already in a family")
    pending = Invite.query.filter_by(family_id=g.f.id, email=email, accepted_at=None, revoked_at=None).filter(
        db.or_(Invite.expires_at.is_(None), Invite.expires_at > now)
    ).first()
    if pending:
        return err("An invitation is already pending for that email")
    inv = Invite(family_id=g.f.id, email=email, role=role, inviter_id=g.u.id,
                 expires_at=datetime.utcnow() + timedelta(days=7))
    db.session.add(inv)
    db.session.flush()
    inv.token_nonce = secrets.token_urlsafe(24)
    raw = invite_ser.dumps({"id": inv.id, "nonce": inv.token_nonce})
    inv.token_hash = hashlib.sha256(raw.encode()).hexdigest()
    try:
        link = invitation_link(inv)
        db.session.commit()
    except (RuntimeError, ValueError) as exc:
        db.session.rollback()
        app.logger.error("Could not generate invitation URL (%s)", type(exc).__name__)
        return err("Invitation URL is not configured correctly. Update APP_BASE_URL and try again.", 503)
    delivery = send_and_record_invitation(inv, link)
    return jsonify(ok=1, invitation={"id": inv.id, "email": email, "status": "pending",
                                     "role": inv.role, "expires": inv.expires_at.isoformat(),
                                     "link": link, "delivery": delivery})


@app.get("/api/invitations/<token>")
def invitation_info(token):
    inv = invitation_from_token(token)
    if not inv or inv.revoked_at or inv.accepted_at or (inv.expires_at and inv.expires_at <= datetime.utcnow()):
        return err("This invitation is invalid, expired, or no longer available", 404)
    family = db.session.get(Family, inv.family_id)
    inviter = db.session.get(User, inv.inviter_id) if inv.inviter_id else None
    return jsonify(email=inv.email, family=family.name if family else "",
                   inviter=inviter.name if inviter else None,
                   expires=inv.expires_at.isoformat() if inv.expires_at else None)


@app.post("/api/invitations/<token>/accept")
@auth
def accept_invitation(token):
    inv = invitation_from_token(token)
    if not inv:
        return err("This invitation is invalid, expired, or no longer available", 404)
    if g.u.email.lower() != inv.email.lower():
        return err("Sign in with the email address this invitation was sent to", 403)
    if inv.accepted_at:
        if g.u.family_id == inv.family_id:
            return jsonify(ok=1, already_accepted=True)
        return err("This invitation is invalid, expired, or no longer available", 404)
    if inv.revoked_at or (inv.expires_at and inv.expires_at <= datetime.utcnow()):
        return err("This invitation is invalid, expired, or no longer available", 404)
    if g.u.family_id:
        return err("You already belong to a family", 409)
    family = db.session.get(Family, inv.family_id)
    used = User.query.filter_by(family_id=inv.family_id).count()
    if not family or used >= LIMIT.get(family.plan, LIMIT["free"]):
        return err("This family has reached its member limit", 409)
    g.u.family_id, g.u.role = inv.family_id, inv.role or "Member"
    inv.accepted_at = datetime.utcnow()
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/invitations/<int:i>/revoke")
@fam
def revoke_invitation(i):
    if not g.u.is_owner:
        return err("Only the family owner can cancel invitations", 403)
    inv = Invite.query.filter_by(id=i, family_id=g.f.id, accepted_at=None).first_or_404()
    inv.revoked_at = datetime.utcnow()
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/invitations/<int:i>/resend")
@fam
def resend_invitation(i):
    if not g.u.is_owner:
        return err("Only the family owner can resend invitations", 403)
    inv = Invite.query.filter_by(id=i, family_id=g.f.id, accepted_at=None, revoked_at=None).first_or_404()
    if inv.delivery_attempted_at and inv.delivery_attempted_at > datetime.utcnow() - timedelta(minutes=1):
        return err("This invitation was just emailed. Wait a minute before resending.", 429)
    inv.expires_at = datetime.utcnow() + timedelta(days=7)
    inv.token_nonce = secrets.token_urlsafe(24)
    replacement = invite_ser.dumps({"id": inv.id, "nonce": inv.token_nonce})
    inv.token_hash = hashlib.sha256(replacement.encode()).hexdigest()
    try:
        link = invitation_link(inv)
        db.session.commit()
    except (RuntimeError, ValueError):
        db.session.rollback()
        return err("Invitation URL is not configured correctly. Update APP_BASE_URL and try again.", 503)
    delivery = send_and_record_invitation(inv, link)
    return jsonify(ok=1, link=link, expires=inv.expires_at.isoformat(), delivery=delivery)


@app.post("/api/upgrade")
@fam
def upgrade():
    # shortcut: simulated payment for class demos (DEMO_PAYMENTS=1); real billing goes through /api/subscriptions/checkout
    if not g.u.is_owner:
        return err("Only the family owner can manage billing", 403)
    if os.environ.get("DEMO_PAYMENTS") != "1":
        return err("Premium activation requires a verified payment. Demo payments are turned off on this server.", 503)
    if g.f.plan == "premium":
        return err("Your family is already on Premium", 409)
    period = body().get("period")
    if period not in ("monthly", "annual"):
        return err("Choose monthly or annual billing")
    db.session.add(Subscription(family_id=g.f.id, plan="premium", period=period,
                                amount=99 if period == "monthly" else 999, status="active", payment_method="demo"))
    g.f.plan = "premium"
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/downgrade")
@fam
def downgrade():
    if not g.u.is_owner:
        return err("Only the family owner can manage billing", 403)
    if g.f.plan != "premium":
        return err("Your family is already on the Free plan", 409)
    if User.query.filter_by(family_id=g.f.id).count() > LIMIT["free"]:
        return err(f"The Free plan allows {LIMIT['free']} members. Remove members before switching.", 409)
    for sub in Subscription.query.filter_by(family_id=g.f.id, status="active"):
        sub.status = "cancelled"
    g.f.plan = "free"
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/subscriptions/checkout")
@fam
def checkout():
    if not g.u.is_owner:
        return err("Only the family owner can manage billing", 403)
    d = body()
    period = d.get("period")
    if period not in ("monthly", "annual"):
        return err("Choose monthly or annual billing")
    method = d.get("payment_method")
    if method not in ("card", "paymaya"):
        return err("Choose a supported payment method")
    if not os.environ.get("PAYMENT_PUBLIC_KEY"):
        return err("PayMongo public key is not configured. No payment was created.", 503)
    plan_id = os.environ.get("PAYMONGO_PLAN_MONTHLY_ID" if period == "monthly" else "PAYMONGO_PLAN_ANNUAL_ID", "")
    if not plan_id:
        return err("PayMongo plan IDs are not configured. Create the test plans and add their IDs before checkout.", 503)
    amount = 99 if period == "monthly" else 999
    try:
        plan = paymongo_request("GET", f"/subscriptions/plans/{plan_id}").get("data", {}).get("attributes", {})
        expected_intervals = {"monthly": {"monthly", "month"}, "annual": {"yearly", "year"}}
        if (plan.get("currency") != "PHP" or plan.get("amount") != amount * 100
                or plan.get("interval") not in expected_intervals[period]
                or plan.get("interval_count", 1) != 1):
            return err("The configured PayMongo plan does not match this Gastos price. Checkout was not started.", 503)
        active = Subscription.query.filter_by(family_id=g.f.id, status="active").order_by(Subscription.id.desc()).first()
        if active:
            return err("This family already has an active Premium subscription", 409)
        pending = Subscription.query.filter(
            Subscription.family_id == g.f.id,
            Subscription.status.in_(("pending_payment", "incomplete")),
        ).order_by(Subscription.id.desc()).first()
        if pending:
            if pending.period != period or pending.payment_method != method or not pending.provider_reference or not pending.payment_intent_id:
                return err("A payment is already awaiting completion. Finish or cancel it before starting another.", 409)
            provider_subscription = paymongo_request("GET", f"/subscriptions/{pending.provider_reference}").get("data", {})
            pi = paymongo_request("GET", f"/payment_intents/{pending.payment_intent_id}").get("data", {}).get("attributes", {})
            attributes = provider_subscription.get("attributes", {})
            apply_subscription_status(pending, attributes.get("status", pending.status))
            db.session.commit()
            if attributes.get("status") != "incomplete":
                return err("The previous payment attempt is no longer available. Please start checkout again.", 409)
            local_subscription = pending
            client_key = pi.get("client_key")
        else:
            family = db.session.get(Family, g.f.id)
            if not family.paymongo_customer_id:
                name_parts = (g.u.name or "Gastos Member").split(maxsplit=1)
                customer = paymongo_request("POST", "/customers", {"data": {"attributes": {
                    "first_name": name_parts[0][:120], "last_name": name_parts[1][:120] if len(name_parts) > 1 else "",
                    "email": g.u.email,
                }}}, f"gastos-family-customer-{family.id}").get("data", {})
                family.paymongo_customer_id = customer.get("id")
                if not family.paymongo_customer_id:
                    raise PayMongoError()
                db.session.commit()
            local_subscription = Subscription(family_id=family.id, plan="premium", period=period,
                                              amount=amount, status="pending_payment", payment_method=method)
            db.session.add(local_subscription)
            db.session.commit()
            result = paymongo_request("POST", "/subscriptions", {"data": {"attributes": {
                "plan_id": plan_id, "customer_id": family.paymongo_customer_id,
            }}}, f"gastos-subscription-{local_subscription.id}").get("data", {})
            attributes = result.get("attributes", {})
            invoice = attributes.get("latest_invoice", {})
            payment_intent_id = (invoice.get("payment_intent") or {}).get("id")
            if not result.get("id") or not payment_intent_id:
                raise PayMongoError()
            local_subscription.provider_reference = result["id"]
            local_subscription.payment_intent_id = payment_intent_id
            apply_subscription_status(local_subscription, attributes.get("status", "incomplete"))
            db.session.commit()
            pi = paymongo_request("GET", f"/payment_intents/{payment_intent_id}").get("data", {}).get("attributes", {})
            client_key = pi.get("client_key")
        if not client_key:
            return err("PayMongo did not return a client payment token. No payment was confirmed.", 502)
        try:
            return_url = public_app_link({"payment": str(local_subscription.id)})
        except (RuntimeError, ValueError):
            return err("APP_BASE_URL must be a reachable HTTPS address before payment checkout.", 503)
        return jsonify(ok=1, subscription_id=local_subscription.id,
                       payment_intent_id=local_subscription.payment_intent_id,
                       client_key=client_key, public_key=os.environ["PAYMENT_PUBLIC_KEY"],
                       payment_method=method, amount=amount, currency="PHP", return_url=return_url)
    except PayMongoError as exc:
        db.session.rollback()
        failed_local = locals().get("local_subscription")
        if failed_local and failed_local.id:
            failed_local = db.session.get(Subscription, failed_local.id)
            if failed_local and not failed_local.provider_reference:
                failed_local.status = "failed"
                db.session.commit()
        app.logger.error("PayMongo checkout request failed (HTTP %s)", exc.status or "network")
        return err("PayMongo could not start checkout. Confirm Subscriptions is enabled for this test account and try again.", 503)


@app.get("/api/subscriptions/status")
@fam
def subscription_status():
    local = Subscription.query.filter_by(family_id=g.f.id).order_by(Subscription.id.desc()).first()
    if not local:
        return jsonify(status="free", plan="free")
    if local.provider_reference and os.environ.get("PAYMENT_PROVIDER_SECRET"):
        try:
            result = paymongo_request("GET", f"/subscriptions/{local.provider_reference}").get("data", {})
            apply_subscription_status(local, result.get("attributes", {}).get("status", local.status))
            db.session.commit()
        except PayMongoError as exc:
            app.logger.warning("PayMongo status refresh failed (HTTP %s)", exc.status or "network")
    return jsonify(status=local.status, plan=local.plan, period=local.period, amount=local.amount)


@app.post("/api/subscriptions/cancel")
@fam
def subscription_cancel():
    if not g.u.is_owner:
        return err("Only the family owner can manage billing", 403)
    local = Subscription.query.filter_by(family_id=g.f.id).order_by(Subscription.id.desc()).first()
    if not local or not local.provider_reference or local.status not in ("active", "past_due", "incomplete", "pending_payment"):
        return err("There is no cancellable subscription", 404)
    try:
        paymongo_request("DELETE", f"/subscriptions/{local.provider_reference}")
    except PayMongoError as exc:
        app.logger.error("PayMongo cancellation failed (HTTP %s)", exc.status or "network")
        return err("PayMongo could not cancel the subscription. Please try again.", 503)
    apply_subscription_status(local, "cancelled")
    db.session.commit()
    return jsonify(ok=1, status="cancelled")


@app.post("/webhooks/paymongo")
def paymongo_webhook():
    webhook_secret = os.environ.get("PAYMONGO_WEBHOOK_SECRET", "")
    api_secret = os.environ.get("PAYMENT_PROVIDER_SECRET", "")
    signature_header = request.headers.get("Paymongo-Signature", "")
    if not webhook_secret or not api_secret:
        return err("Webhook is not configured", 503)
    try:
        parts = dict(piece.strip().split("=", 1) for piece in signature_header.split(",") if "=" in piece)
        timestamp = parts.get("t", "")
        event_time = int(timestamp)
        raw = request.get_data(cache=True, as_text=False)
        if abs(time.time() - event_time) > 300:
            return err("Webhook timestamp is outside the allowed window", 401)
        mode = "li" if api_secret.startswith("sk_live_") else "te"
        supplied = parts.get(mode, "")
        expected = hmac.new(webhook_secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        if not supplied or not hmac.compare_digest(supplied, expected):
            return err("Invalid PayMongo signature", 401)
        envelope = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError):
        return err("Malformed PayMongo webhook", 400)
    event = envelope.get("data", {}) if isinstance(envelope, dict) else {}
    if not isinstance(event, dict):
        return err("Malformed PayMongo event", 400)
    event_id = event.get("id")
    event_attributes = event.get("attributes", {})
    if not isinstance(event_attributes, dict):
        return err("Malformed PayMongo event", 400)
    event_type = event_attributes.get("type", "")
    if event_attributes.get("livemode") is not None and bool(event_attributes.get("livemode")) != api_secret.startswith("sk_live_"):
        return err("Webhook mode does not match this server", 401)
    resource = event_attributes.get("data", {})
    if not isinstance(resource, dict):
        return err("Malformed PayMongo resource", 400)
    resource_attributes = resource.get("attributes", {})
    if not isinstance(resource_attributes, dict):
        return err("Malformed PayMongo resource", 400)
    if not event_id:
        return err("PayMongo event ID is missing", 400)
    if WebhookEvent.query.filter_by(provider_event_id=event_id).first():
        return jsonify(ok=1, duplicate=True)
    subscription_id = resource.get("id") if event_type.startswith("subscription.") else resource_attributes.get("resource_id")
    local = Subscription.query.filter_by(provider_reference=subscription_id).first() if subscription_id else None
    try:
        if local:
            provider_status = {
                "subscription.activated": "active",
                "subscription.past_due": "past_due",
                "subscription.unpaid": "unpaid",
                "subscription.invoice.paid": "active",
                "subscription.invoice.payment_failed": "past_due",
            }.get(event_type)
            if event_type == "subscription.updated":
                provider_status = resource_attributes.get("status")
            if provider_status:
                apply_subscription_status(local, provider_status)
        db.session.add(WebhookEvent(provider_event_id=event_id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("PayMongo webhook processing failed")
        return err("Webhook processing failed", 500)
    return jsonify(ok=1)


def num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = 0
    if not math.isfinite(x) or x <= 0:
        raise ValueError("Enter an amount greater than 0")
    if x > 1_000_000_000:  # larger values overflow the dashboard percentage maths
        raise ValueError("Enter an amount up to ₱1,000,000,000")
    return x


def needs_approval(kind):
    """Premium families: expenses logged by non-owners wait for the owner's approval."""
    return premium() and not g.u.is_owner and kind == "expense"


def apply_receipt(row, d):
    """Set or clear row.receipt_data from the request; returns an error message or None."""
    if "receipt_data" not in d:
        return None
    value = d["receipt_data"]
    if value == "":
        row.receipt_data = None
        return None
    if not premium():
        return "Receipt scanning is a Premium feature"
    problem = image_data_url(value) if isinstance(value, str) else "The receipt photo format is invalid"
    if problem:
        return problem
    row.receipt_data = value
    return None


def pdate(s):
    try:
        return date.fromisoformat(s) if s else app_today()
    except (TypeError, ValueError):
        raise ValueError("Enter a valid date")


def num0(v):
    """Like num(), but 0 is allowed (opening balances and balance corrections)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid amount")
    if not math.isfinite(x) or x < 0:
        raise ValueError("Enter an amount of 0 or more")
    if x > 1_000_000_000:
        raise ValueError("Enter an amount up to ₱1,000,000,000")
    return x


def wallet_from(d, owner_id):
    """The wallet_id sent with a transaction: (id or None, error or None). It must be one of the owner's own wallets."""
    raw = d.get("wallet_id")
    if raw in (None, ""):
        return None, None
    try:
        wid = int(raw)
    except (TypeError, ValueError):
        return None, "Choose one of your own wallets"
    if not Wallet.query.filter_by(id=wid, user_id=owner_id).first():
        return None, "Choose one of your own wallets"
    return wid, None


def tx_row(r, members, wallet_names):
    return {"id": r.id, "kind": r.kind, "amount": r.amount, "category": r.category,
            "note": r.note, "date": r.date.isoformat(), "member": members.get(r.user_id, "Family member"),
            "status": r.status, "has_receipt": bool(r.receipt_data),
            "wallet_id": r.wallet_id if r.wallet_id in wallet_names else None, "wallet": wallet_names.get(r.wallet_id),
            "mine": r.user_id == g.u.id, "can_edit": bool(g.u.is_owner or r.user_id == g.u.id)}


@app.route("/api/transactions", methods=["GET", "POST"])
@fam
def txs():
    if request.method == "POST":
        d = body()
        try:
            amt = num(d.get("amount"))
            tx_date = pdate(d.get("date"))
        except ValueError as e:
            return err(str(e))
        if d.get("kind") not in ("income", "expense"):
            return err("Choose income or expense")
        kind = d["kind"]
        category = d.get("category") if isinstance(d.get("category"), str) else "Other"
        note = d.get("note") if isinstance(d.get("note"), str) else ""
        wallet_id, problem = wallet_from(d, g.u.id)
        if problem:
            return err(problem)
        row = Tx(family_id=g.f.id, user_id=g.u.id, kind=kind, amount=amt,
                 category=(category or "Other")[:60], note=note[:200], date=tx_date,
                 status="pending" if needs_approval(kind) else "approved", wallet_id=wallet_id)
        problem = apply_receipt(row, d)
        if problem:
            return err(problem)
        db.session.add(row)
        db.session.commit()
        return jsonify(ok=1, status=row.status)
    rows = Tx.query.filter_by(family_id=g.f.id).order_by(Tx.date.desc(), Tx.id.desc()).limit(100)
    members = {u.id: u.name for u in User.query.filter_by(family_id=g.f.id)}
    wallet_names = {w.id: w.name for w in Wallet.query.filter_by(user_id=g.u.id)}
    return jsonify([tx_row(r, members, wallet_names) for r in rows])


@app.route("/api/transactions/<int:i>", methods=["GET", "PUT", "DELETE"])
@fam
def tx_detail(i):
    row = Tx.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    if request.method == "GET":
        if not can_manage_finances() and row.user_id != g.u.id:
            return err("Members can only view their own transaction details", 403)
    elif not g.u.is_owner and row.user_id != g.u.id:
        return err("Members can only edit or delete their own transactions", 403)
    if request.method == "DELETE":
        try:
            db.session.delete(row)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Transaction deletion failed")
            return err("Could not delete this transaction. Please refresh and try again.", 500)
        return jsonify(ok=1)
    if request.method == "PUT":
        d = body()
        try:
            row.amount = num(d.get("amount"))
            row.date = pdate(d.get("date"))
        except ValueError as e:
            return err(str(e))
        if d.get("kind") not in ("income", "expense"):
            return err("Choose income or expense")
        category = d.get("category") if isinstance(d.get("category"), str) else "Other"
        note = d.get("note") if isinstance(d.get("note"), str) else ""
        row.kind, row.category, row.note = d["kind"], (category or "Other")[:60], note[:200]
        if "wallet_id" in d:
            wallet_id, problem = wallet_from(d, row.user_id)
            if problem:
                db.session.rollback()
                return err(problem)
            row.wallet_id = wallet_id
        row.status = "pending" if needs_approval(row.kind) else "approved"
        problem = apply_receipt(row, d)
        if problem:
            db.session.rollback()
            return err(problem)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Transaction update failed")
            return err("Could not save these changes. Please refresh and try again.", 500)
        return jsonify(ok=1, status=row.status)
    return jsonify(id=row.id, kind=row.kind, amount=row.amount, category=row.category,
                   note=row.note, date=row.date.isoformat(), status=row.status, receipt_data=row.receipt_data,
                   wallet_id=row.wallet_id if row.user_id == g.u.id else None, mine=row.user_id == g.u.id)


@app.post("/api/transactions/<int:i>/<any(approve, reject):decision>")
@fam
def tx_decide(i, decision):
    if not can_manage_finances():
        return err("Only a Parent or the family owner can approve expenses", 403)
    row = Tx.query.filter_by(id=i, family_id=g.f.id, status="pending").first_or_404()
    if not g.u.is_owner and row.user_id == g.u.id:
        return err("You cannot approve your own expense", 403)
    row.status = "approved" if decision == "approve" else "rejected"
    db.session.commit()
    return jsonify(ok=1, status=row.status)


def summarize(rows):
    inc = sum(r.amount for r in rows if r.kind == "income")
    exp = sum(r.amount for r in rows if r.kind == "expense")
    cats = {}
    for r in rows:
        if r.kind == "expense":
            cats[r.category] = cats.get(r.category, 0) + r.amount
    return {"income": inc, "expense": exp, "balance": inc - exp,
            "cats": {k: round(v * 100 / exp) for k, v in cats.items()} if exp else {}}


def year_rows(y):
    return approved_tx().filter(Tx.date >= date(y, 1, 1), Tx.date <= date(y, 12, 31)).all()


@app.get("/api/dashboard")
@fam
def dash():
    t = app_today()
    rows = approved_tx().order_by(Tx.date.desc(), Tx.id.desc()).all()
    current = [r for r in rows if r.date.year == t.year and r.date.month == t.month]
    totals = summarize(current)
    categories = {}
    for row in current:
        if row.kind == "expense":
            categories[row.category] = categories.get(row.category, 0) + row.amount
    months = []
    for offset in range(5, -1, -1):
        index = t.year * 12 + t.month - 1 - offset
        year, month = divmod(index, 12)
        month += 1
        summary = summarize([r for r in rows if r.date.year == year and r.date.month == month])
        months.append({"label": date(year, month, 1).strftime("%b"),
                       "income": summary["income"], "expense": summary["expense"]})
    goals = Goal.query.filter_by(family_id=g.f.id).all()
    saved, target = sum(x.saved for x in goals), sum(x.target for x in goals)
    members = {u.id: u.name for u in User.query.filter_by(family_id=g.f.id)}
    wallet_data = wallet_overview()
    wallet_names = {w["id"]: w["name"] for w in wallet_data["wallets"]}
    recent = [{"kind": r.kind, "amount": r.amount, "category": r.category, "note": r.note,
               "date": r.date.isoformat(), "member": members.get(r.user_id, "Family member"),
               "wallet": wallet_names.get(r.wallet_id)}
              for r in rows[:6]]
    bills = [{"id": b.id, "name": b.name, "amount": b.amount, "due": b.due.isoformat(),
              "overdue": b.due < t,
              "due_status": "overdue" if b.due < t else "due_today" if b.due == t else "upcoming"}
             for b in Bill.query.filter_by(family_id=g.f.id, paid=False).order_by(Bill.due).limit(5)]
    budget_rows = Budget.query.filter_by(family_id=g.f.id).order_by(Budget.category).all()
    budget_progress = []
    for budget in budget_rows:
        spent = sum(r.amount for r in current if r.kind == "expense" and r.category == budget.category)
        ratio = round(spent * 100 / budget.monthly_limit) if budget.monthly_limit else 0
        budget_progress.append({"id": budget.id, "category": budget.category, "limit": budget.monthly_limit,
                               "spent": spent, "percent": ratio,
                               "status": "exceeded" if ratio >= 100 else "approaching" if ratio >= 80 else "normal"})
    approvals = [{"id": r.id, "kind": r.kind, "amount": r.amount, "category": r.category, "note": r.note,
                  "date": r.date.isoformat(), "member": members.get(r.user_id, "Family member"),
                  "has_receipt": bool(r.receipt_data)}
                 for r in Tx.query.filter_by(family_id=g.f.id, status="pending").order_by(Tx.date.desc())] if can_manage_finances() else []
    totals.update(category_totals=categories, months=months, recent=recent, bills=bills,
                   budgets=budget_progress, approvals=approvals,
                   wallets=wallet_data["wallets"][:3], wallet_count=len(wallet_data["wallets"]),
                   wallet_totals=wallet_data["totals"],
                   savings={"saved": saved, "target": target,
                            "percent": min(100, round(saved * 100 / target)) if target else 0})
    return jsonify(totals)


@app.get("/api/reports")
@fam
def reports():
    t = app_today()
    rows = year_rows(t.year)
    goals = Goal.query.filter_by(family_id=g.f.id).all()
    tgt = sum(x.target for x in goals)
    months = {m: summarize([r for r in rows if r.date.month == m]) for m in range(1, t.month + 1)}
    month_rows = [r for r in rows if r.date.month == t.month and r.kind == "expense"]
    category_totals = {}
    for row in month_rows:
        category_totals[row.category] = category_totals.get(row.category, 0) + row.amount
    advanced = None
    if premium():
        first = t.replace(day=1)
        prev_first = (first - timedelta(days=1)).replace(day=1)
        last_month, by_member = {}, {}
        for r in approved_tx().filter(Tx.kind == "expense", Tx.date >= prev_first, Tx.date < first):
            last_month[r.category] = last_month.get(r.category, 0) + r.amount
        members = {u.id: u.name for u in User.query.filter_by(family_id=g.f.id)}
        for r in month_rows:
            name = members.get(r.user_id, "Family member")
            by_member[name] = by_member.get(name, 0) + r.amount
        days_in_month = ((first + timedelta(days=32)).replace(day=1) - first).days
        daily = sum(category_totals.values()) / t.day
        advanced = {"daily_average": daily, "projected": daily * days_in_month,
                    "last_month": last_month, "last_month_total": sum(last_month.values()),
                    "by_member": by_member}
    return jsonify(month=summarize([r for r in rows if r.date.month == t.month]),
                   year=summarize(rows), months=months,
                   category_totals=category_totals, advanced=advanced,
                   savings=round(sum(x.saved for x in goals) * 100 / tgt) if tgt else 0)


def csv_cell(v):
    """Stop spreadsheet apps from running a note like =HYPERLINK(...) as a formula."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


@app.get("/api/export")
@fam
def export():
    if not premium():
        return err("Data export is a Premium feature", 403)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "type", "category", "amount", "note"])
    for r in approved_tx().order_by(Tx.date):
        w.writerow([r.date, r.kind, csv_cell(r.category), r.amount, csv_cell(r.note)])
    return Response(out.getvalue(), mimetype="text/csv")


@app.route("/api/bills", methods=["GET", "POST"])
@fam
def bills():
    if request.method == "POST":
        if not can_manage_finances():
            return err("Only a Parent or the family owner can manage bills", 403)
        d = body()
        try:
            amt = num(d.get("amount"))
            due = pdate(d.get("due"))
        except ValueError as e:
            return err(str(e))
        name = d.get("name") if isinstance(d.get("name"), str) else ""
        if not name.strip():
            return err("Bill name required")
        db.session.add(Bill(family_id=g.f.id, name=name.strip()[:120], amount=amt, due=due))
        db.session.commit()
        return jsonify(ok=1)
    rows = Bill.query.filter_by(family_id=g.f.id, paid=False).order_by(Bill.due)
    t = app_today()
    return jsonify([{"id": b.id, "name": b.name, "amount": b.amount, "due": b.due.isoformat(),
                     "due_status": "overdue" if b.due < t else "due_today" if b.due == t else "upcoming"}
                    for b in rows])


@app.route("/api/bills/<int:i>", methods=["GET", "PUT", "DELETE"])
@fam
def bill_detail(i):
    bill = Bill.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    if request.method != "GET" and not can_manage_finances():
        return err("Only a Parent or the family owner can manage bills", 403)
    if bill.paid:
        return err("Paid bills can no longer be changed", 409)
    if request.method == "DELETE":
        db.session.delete(bill)
        db.session.commit()
        return jsonify(ok=1)
    if request.method == "PUT":
        d = body()
        name = d.get("name") if isinstance(d.get("name"), str) else ""
        if not name.strip():
            return err("Bill name required")
        try:
            amount, due = num(d.get("amount")), pdate(d.get("due"))
        except ValueError as e:
            return err(str(e))
        bill.name, bill.amount, bill.due = name.strip()[:120], amount, due
        db.session.commit()
        return jsonify(ok=1)
    return jsonify(id=bill.id, name=bill.name, amount=bill.amount, due=bill.due.isoformat())


@app.post("/api/bills/<int:i>/pay")
@fam
def pay(i):
    if not can_manage_finances():
        return err("Only a Parent or the family owner can mark bills as paid", 403)
    b = Bill.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    if b.paid:
        return err("This bill has already been paid", 409)
    b.paid = True
    db.session.add(Tx(family_id=g.f.id, user_id=g.u.id, kind="expense", amount=b.amount,
                      category="Bills", note=b.name, date=app_today()))
    db.session.commit()
    return jsonify(ok=1)


@app.route("/api/goals", methods=["GET", "POST"])
@fam
def goals():
    if request.method == "POST":
        if not can_manage_finances():
            return err("Only a Parent or the family owner can create savings goals", 403)
        d = body()
        try:
            tgt = num(d.get("target"))
        except ValueError as e:
            return err(str(e))
        name = d.get("name") if isinstance(d.get("name"), str) else ""
        if not name.strip():
            return err("Goal name required")
        db.session.add(Goal(family_id=g.f.id, name=name.strip()[:120], target=tgt, saved=0))
        db.session.commit()
        return jsonify(ok=1)
    return jsonify([{"id": x.id, "name": x.name, "target": x.target, "saved": x.saved}
                    for x in Goal.query.filter_by(family_id=g.f.id)])


@app.post("/api/goals/<int:i>/add")
@fam
def goal_add(i):
    x = Goal.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    try:
        x.saved += num(body().get("amount"))
    except ValueError as e:
        return err(str(e))
    db.session.commit()
    return jsonify(ok=1)


@app.route("/api/budgets", methods=["GET", "POST"])
@fam
def budgets():
    if request.method == "POST":
        if not can_manage_finances():
            return err("Only a Parent or the family owner can manage budgets", 403)
        d = body()
        category = d.get("category") if isinstance(d.get("category"), str) else ""
        if not category.strip() or len(category.strip()) > 60:
            return err("Enter a valid budget category")
        try:
            monthly_limit = num(d.get("monthly_limit"))
        except ValueError as e:
            return err(str(e))
        budget = Budget.query.filter_by(family_id=g.f.id, category=category.strip()).first()
        if budget:
            budget.monthly_limit = monthly_limit
        elif not premium() and Budget.query.filter_by(family_id=g.f.id).count() >= FREE_BUDGETS:
            return err(f"The Free plan includes {FREE_BUDGETS} budgets. Upgrade to Premium for unlimited budgets.", 403)
        else:
            budget = Budget(family_id=g.f.id, category=category.strip(), monthly_limit=monthly_limit)
            db.session.add(budget)
        db.session.commit()
        return jsonify(ok=1, id=budget.id)
    t = app_today()
    spent = {}
    for row in approved_tx().filter(Tx.kind == "expense", Tx.date >= t.replace(day=1), Tx.date <= t):
        spent[row.category] = spent.get(row.category, 0) + row.amount
    return jsonify([{"id": b.id, "category": b.category, "monthly_limit": b.monthly_limit,
                     "spent": spent.get(b.category, 0)}
                    for b in Budget.query.filter_by(family_id=g.f.id).order_by(Budget.category)])


@app.route("/api/budgets/<int:i>", methods=["PUT", "DELETE"])
@fam
def budget_detail(i):
    if not can_manage_finances():
        return err("Only a Parent or the family owner can manage budgets", 403)
    budget = Budget.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    if request.method == "DELETE":
        db.session.delete(budget)
        db.session.commit()
        return jsonify(ok=1)
    d = body()
    category = d.get("category") if isinstance(d.get("category"), str) else ""
    if not category.strip() or len(category.strip()) > 60:
        return err("Enter a valid budget category")
    try:
        monthly_limit = num(d.get("monthly_limit"))
    except ValueError as e:
        return err(str(e))
    other = Budget.query.filter(Budget.family_id == g.f.id, Budget.category == category.strip(), Budget.id != i).first()
    if other:
        return err("A budget already exists for that category")
    budget.category, budget.monthly_limit = category.strip(), monthly_limit
    db.session.commit()
    return jsonify(ok=1)


# ---------- Bank wallets: Cash Wallet and Card Wallet (one set per user account) ----------

def wallet_sums(since=None):
    """{wallet_id: {"income": x, "expense": y}} for the signed-in account's approved, wallet-linked transactions."""
    q = db.session.query(Tx.wallet_id, Tx.kind, db.func.sum(Tx.amount)).filter(
        Tx.user_id == g.u.id, Tx.status == "approved", Tx.wallet_id.isnot(None))
    if since:
        q = q.filter(Tx.date >= since)
    out = {}
    for wid, kind, total in q.group_by(Tx.wallet_id, Tx.kind):
        out.setdefault(wid, {"income": 0.0, "expense": 0.0})[kind] = float(total or 0)
    return out


def is_credit(w):
    return w.kind == "card" and w.card_type == "credit"


def wallet_json(w, sums, month_sums):
    s, m = sums.get(w.id, {}), month_sums.get(w.id, {})
    income, expense = s.get("income", 0.0), s.get("expense", 0.0)
    balance = round((w.opening_balance or 0) + income - expense, 2)
    out = {"id": w.id, "kind": w.kind, "name": w.name, "bank": w.bank, "card_type": w.card_type,
           "last4": w.last4, "credit_limit": w.credit_limit, "balance": balance,
           "income": income, "expense": expense,
           "month_income": m.get("income", 0.0), "month_expense": m.get("expense", 0.0)}
    if is_credit(w):
        out["owed"] = round(max(0.0, -balance), 2)
        out["available"] = round(max(0.0, w.credit_limit + balance), 2) if w.credit_limit else None
    return out


def wallet_overview():
    """The signed-in account's wallets (cash first) with live balances, plus totals."""
    sums, month_sums = wallet_sums(), wallet_sums(app_today().replace(day=1))
    rows = sorted(Wallet.query.filter_by(user_id=g.u.id).all(), key=lambda w: (w.kind != "cash", w.id))
    wallets = [wallet_json(w, sums, month_sums) for w in rows]
    cash = sum(w["balance"] for w in wallets if w["kind"] == "cash")
    debit = sum(w["balance"] for w in wallets if w["kind"] == "card" and w["card_type"] != "credit")
    owed = sum(w["owed"] for w in wallets if w["card_type"] == "credit" and w["kind"] == "card")
    return {"wallets": wallets, "totals": {"cash": round(cash, 2), "debit": round(debit, 2),
                                           "available": round(cash + debit, 2), "owed": round(owed, 2)}}


def parse_wallet(d, kind, with_balance=True):
    """Validated wallet fields from a request body. Raises ValueError with a user-facing message."""
    name = d.get("name") if isinstance(d.get("name"), str) else ""
    name = name.strip()
    if not name:
        raise ValueError("Wallet name required")
    if len(name) > 80:
        raise ValueError("Wallet name must be 80 characters or fewer")
    out = {"name": name}
    raw = d.get("opening_balance")
    amount = 0.0 if raw in (None, "") else num0(raw)
    if kind == "cash":
        out.update(bank=None, card_type=None, last4=None, credit_limit=None)
        if with_balance:
            out["opening_balance"] = amount
        return out
    bank = d.get("bank") if isinstance(d.get("bank"), str) else ""
    out["bank"] = bank.strip()[:80] or None
    card_type = d.get("card_type")
    if card_type not in ("debit", "credit"):
        raise ValueError("Choose debit or credit")
    last4 = str(d.get("last4") if d.get("last4") is not None else "").strip()
    if not re.fullmatch(r"\d{4}", last4):
        raise ValueError("Enter only the last 4 digits of the card")
    out.update(card_type=card_type, last4=last4)
    limit = d.get("credit_limit")
    out["credit_limit"] = num(limit) if card_type == "credit" and limit not in (None, "") else None
    if with_balance:
        out["opening_balance"] = -amount if card_type == "credit" else amount  # credit: stored as money owed
    return out


def own_wallet(i):
    return Wallet.query.filter_by(id=i, user_id=g.u.id).first_or_404()


@app.route("/api/wallets", methods=["GET", "POST"])
@fam
def wallets():
    if request.method == "POST":
        d = body()
        kind = d.get("kind")
        if kind not in ("cash", "card"):
            return err("Choose a cash wallet or a card")
        if Wallet.query.filter_by(user_id=g.u.id).count() >= MAX_WALLETS:
            return err(f"An account can have up to {MAX_WALLETS} wallets")
        try:
            fields = parse_wallet(d, kind)
        except ValueError as e:
            return err(str(e))
        wallet = Wallet(user_id=g.u.id, kind=kind, **fields)
        db.session.add(wallet)
        db.session.commit()
        return jsonify(ok=1, id=wallet.id)
    return jsonify(wallet_overview())


@app.route("/api/wallets/<int:i>", methods=["GET", "PUT", "DELETE"])
@fam
def wallet_detail(i):
    wallet = own_wallet(i)
    if request.method == "DELETE":
        # The transactions stay in the family's history; they just stop pointing at this wallet.
        Tx.query.filter_by(user_id=g.u.id, wallet_id=wallet.id).update({"wallet_id": None})
        db.session.delete(wallet)
        db.session.commit()
        return jsonify(ok=1)
    if request.method == "PUT":
        try:
            fields = parse_wallet({**body(), "card_type": wallet.card_type}, wallet.kind, with_balance=False)
        except ValueError as e:
            return err(str(e))
        for key, value in fields.items():
            setattr(wallet, key, value)
        db.session.commit()
        return jsonify(ok=1)
    out = wallet_json(wallet, wallet_sums(), wallet_sums(app_today().replace(day=1)))
    members = {u.id: u.name for u in User.query.filter_by(family_id=g.f.id)}
    rows = Tx.query.filter_by(user_id=g.u.id, wallet_id=wallet.id).order_by(Tx.date.desc(), Tx.id.desc()).limit(30)
    out["transactions"] = [tx_row(r, members, {wallet.id: wallet.name}) for r in rows]
    return jsonify(out)


@app.post("/api/wallets/<int:i>/adjust")
@fam
def wallet_adjust(i):
    """Correct a wallet to match reality: cash/debit balance, or the amount currently owed on a credit card."""
    wallet = own_wallet(i)
    try:
        target = num0(body().get("amount"))
    except ValueError as e:
        return err(str(e))
    s = wallet_sums().get(wallet.id, {})
    flow = s.get("income", 0.0) - s.get("expense", 0.0)
    wallet.opening_balance = round((-target if is_credit(wallet) else target) - flow, 2)
    db.session.commit()
    return jsonify(ok=1)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

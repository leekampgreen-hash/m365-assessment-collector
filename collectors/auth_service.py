"""Authentication service - login, session, TOTP."""
from __future__ import annotations

import bcrypt
import logging
import pyotp
from datetime import datetime, timezone, timedelta
from typing import Optional

from collectors.persistence import open_database_connection

logger = logging.getLogger(__name__)


def get_setting(conn, key: str, default=None):
    """Read a system setting from DB."""
    with conn.cursor() as cur:
        cur.execute("SELECT setting_value, setting_type FROM core.system_setting WHERE setting_key = %s", (key,))
        row = cur.fetchone()
    if not row:
        return default
    value, type_ = row
    if type_ == "INTEGER":
        return int(value)
    if type_ == "BOOLEAN":
        return value.lower() == "true"
    return value


def get_user_by_email(conn, email: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT user_id, email, password_hash, totp_secret, totp_enrolled,
                   role, tenant_id, is_active, failed_login_attempts, locked_until
            FROM auth."user" WHERE email = %s
        ''', (email,))
        row = cur.fetchone()
    if not row:
        return None
    cols = ["user_id", "email", "password_hash", "totp_secret", "totp_enrolled",
            "role", "tenant_id", "is_active", "failed_login_attempts", "locked_until"]
    return dict(zip(cols, row))


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def verify_totp(totp_secret: str, code: str, window: int = 1) -> bool:
    return pyotp.TOTP(totp_secret).verify(code, valid_window=window)


def log_auth_event(conn, event_type: str, user_id=None, tenant_id=None, ip_address=None, user_agent=None, detail=None):
    import json
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO auth.auth_event
            (user_id, tenant_id, event_type, ip_address, user_agent, detail)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (user_id, tenant_id, event_type, ip_address, user_agent, json.dumps(detail) if detail else None))


def create_session(conn, user_id: int, ip_address=None, user_agent=None) -> str:
    ttl = get_setting(conn, "session_ttl_minutes", 60)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO auth.session (user_id, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s) RETURNING session_id
        ''', (user_id, expires_at, ip_address, user_agent))
        return str(cur.fetchone()[0])


def get_session(conn, session_id: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT s.session_id, s.user_id, s.expires_at, s.is_valid,
                   u.email, u.role, u.tenant_id, u.is_active
            FROM auth.session s JOIN auth."user" u ON s.user_id = u.user_id
            WHERE s.session_id = %s
        ''', (session_id,))
        row = cur.fetchone()
    if not row:
        return None
    session = dict(zip(["session_id", "user_id", "expires_at", "is_valid", "email", "role", "tenant_id", "is_active"], row))
    expires = session["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not session["is_valid"] or expires < datetime.now(timezone.utc) or not session["is_active"]:
        return None
    return session


def extend_session(conn, session_id: str):
    ttl = get_setting(conn, "session_ttl_minutes", 60)
    with conn.cursor() as cur:
        cur.execute("UPDATE auth.session SET expires_at = %s, last_active_at = NOW() WHERE session_id = %s AND is_valid = TRUE", (datetime.now(timezone.utc) + timedelta(minutes=ttl), session_id))


def invalidate_session(conn, session_id: str):
    with conn.cursor() as cur:
        cur.execute("UPDATE auth.session SET is_valid = FALSE WHERE session_id = %s", (session_id,))


def increment_failed_attempts(conn, user_id: int) -> int:
    max_attempts = get_setting(conn, "max_login_attempts", 5)
    lockout_minutes = get_setting(conn, "lockout_duration_minutes", 30)
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE auth."user" SET failed_login_attempts = failed_login_attempts + 1,
            locked_until = CASE WHEN failed_login_attempts + 1 >= %s THEN NOW() + INTERVAL '1 minute' * %s ELSE locked_until END
            WHERE user_id = %s RETURNING failed_login_attempts
        ''', (max_attempts, lockout_minutes, user_id))
        return cur.fetchone()[0]


def reset_failed_attempts(conn, user_id: int):
    with conn.cursor() as cur:
        cur.execute('''UPDATE auth."user" SET failed_login_attempts = 0, locked_until = NULL, last_login_at = NOW() WHERE user_id = %s''', (user_id,))


def login(conn, email: str, password: str, totp_code: str, ip_address=None, user_agent=None) -> dict:
    user = get_user_by_email(conn, email)
    if not user:
        log_auth_event(conn, "LOGIN_FAILED", ip_address=ip_address, detail={"reason": "user_not_found", "email": email})
        return {"success": False, "error": "Invalid credentials"}
    locked = user["locked_until"]
    if locked and (locked.replace(tzinfo=timezone.utc) if locked.tzinfo is None else locked) > datetime.now(timezone.utc):
        return {"success": False, "error": "Account is temporarily locked"}
    if not user["is_active"]:
        return {"success": False, "error": "Account is disabled"}
    if not verify_password(password, user["password_hash"]):
        attempts = increment_failed_attempts(conn, user["user_id"])
        log_auth_event(conn, "LOGIN_FAILED", user_id=user["user_id"], ip_address=ip_address, detail={"reason": "wrong_password", "attempts": attempts})
        return {"success": False, "error": "Invalid credentials"}
    if user["totp_enrolled"] and (not totp_code or not verify_totp(user["totp_secret"], totp_code, get_setting(conn, "totp_window", 1))):
        log_auth_event(conn, "MFA_FAILED", user_id=user["user_id"], ip_address=ip_address)
        return {"success": False, "error": "Invalid MFA code"}
    reset_failed_attempts(conn, user["user_id"])
    session_id = create_session(conn, user["user_id"], ip_address, user_agent)
    log_auth_event(conn, "LOGIN_SUCCESS", user_id=user["user_id"], tenant_id=user["tenant_id"], ip_address=ip_address)
    return {"success": True, "session_id": session_id, "user": {key: user[key] for key in ("user_id", "email", "role", "tenant_id", "totp_enrolled")}}

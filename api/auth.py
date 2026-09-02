"""Authentication API helpers and HTTP handler mixin."""
from __future__ import annotations

import json
import os
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler

from collectors import auth_service

API_KEY_HEADER = "X-API-Key"
_API_KEY = os.getenv("API_KEY", "")


def verify_api_key(handler: BaseHTTPRequestHandler) -> bool:
    if not _API_KEY:
        return True
    return handler.headers.get(API_KEY_HEADER) == _API_KEY


def session_id(handler):
    value = handler.headers.get("X-Session-ID")
    if value and value.lower() not in {"null", "undefined"}:
        return value
    cookie = SimpleCookie(handler.headers.get("Cookie", ""))
    cookie_value = cookie.get("session_id").value if cookie.get("session_id") else None
    return cookie_value if cookie_value and cookie_value.lower() not in {"null", "undefined"} else None


def handle_auth(handler, method: str, path: str) -> bool:
    if not path.startswith("/api/auth"):
        return False
    connection = None
    try:
        connection = handler.connection_factory()
        sid = session_id(handler)
        if method == "POST" and path == "/api/auth/login":
            length = int(handler.headers.get("Content-Length", "0"))
            payload = json.loads(handler.rfile.read(length).decode())
            result = auth_service.login(connection, payload.get("email", ""), payload.get("password", ""), payload.get("totp_code", ""), handler.client_address[0], handler.headers.get("User-Agent"))
            if result["success"]:
                connection.commit()
            status = 200 if result["success"] else 401
            if result["success"]:
                body = json.dumps({"session_id": result["session_id"], "user": result["user"]}, default=str).encode()
                handler.send_response(status)
                handler.send_header("Content-Type", "application/json")
                handler.send_header("Set-Cookie", "session_id=%s; HttpOnly; Path=/; SameSite=Strict" % result["session_id"])
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body)
            else:
                handler._write(status, {"error": result["error"]})
            return True
        user_session = auth_service.get_session(connection, sid) if sid else None
        if not user_session:
            handler._write(401, {"error": "Authentication required"})
            return True
        if method == "POST" and path == "/api/auth/logout":
            auth_service.invalidate_session(connection, sid)
            auth_service.log_auth_event(connection, "LOGOUT", user_session["user_id"], user_session["tenant_id"])
            handler._write(200, {"success": True})
            return True
        if method == "GET" and path == "/api/auth/me":
            handler._write(200, {"user": {key: user_session[key] for key in ("user_id", "email", "role", "tenant_id")}})
            return True
        if method == "POST" and path == "/api/auth/totp/setup":
            secret = auth_service.pyotp.random_base32()
            with connection.cursor() as cur:
                cur.execute('UPDATE auth."user" SET totp_secret = %s, totp_enrolled = FALSE WHERE user_id = %s', (secret, user_session["user_id"]))
            handler._write(200, {"totp_uri": auth_service.pyotp.TOTP(secret).provisioning_uri(user_session["email"], issuer_name="M365 Assessment Collector"), "totp_secret": secret})
            return True
        if method == "POST" and path == "/api/auth/totp/verify":
            length = int(handler.headers.get("Content-Length", "0"))
            code = json.loads(handler.rfile.read(length).decode()).get("totp_code", "")
            with connection.cursor() as cur:
                cur.execute('SELECT totp_secret FROM auth."user" WHERE user_id = %s', (user_session["user_id"],))
                secret = cur.fetchone()[0]
                if not secret or not auth_service.verify_totp(secret, code):
                    handler._write(400, {"error": "Invalid MFA code"})
                    return True
                cur.execute('UPDATE auth."user" SET totp_enrolled = TRUE WHERE user_id = %s', (user_session["user_id"],))
            auth_service.log_auth_event(connection, "TOTP_ENROLLED", user_session["user_id"], user_session["tenant_id"])
            handler._write(200, {"success": True})
            return True
        handler._write(404, {"error": "Not found"})
        return True
    except (ValueError, json.JSONDecodeError):
        handler._write(400, {"error": "Invalid request"})
        return True
    finally:
        if connection is not None:
            connection.close()

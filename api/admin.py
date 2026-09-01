"""Admin API: tenant CRUD, user management, feature flags, system settings, collector status."""
from __future__ import annotations

import json
import secrets
import string
from http.server import BaseHTTPRequestHandler

import bcrypt

from api.auth import session_id
from collectors import auth_service


def _write(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _log_audit(conn, actor_user_id, action: str, target_type: str, target_id: str,
               before_state=None, after_state=None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth.admin_audit
                (actor_user_id, action, target_type, target_id, before_state, after_state)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                actor_user_id,
                action,
                target_type,
                str(target_id),
                json.dumps(before_state, default=str) if before_state is not None else None,
                json.dumps(after_state, default=str) if after_state is not None else None,
            ),
        )


def _generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _require_super_admin(conn, handler: BaseHTTPRequestHandler):
    sid = session_id(handler)
    if not sid:
        return None, "Authentication required"
    session = auth_service.get_session(conn, sid)
    if not session:
        return None, "Authentication required"
    if session["role"] != "SUPER_ADMIN":
        return None, "Forbidden"
    return session, None


def handle_admin(handler: BaseHTTPRequestHandler, method: str, path: str) -> bool:
    if not path.startswith("/api/admin"):
        return False
    connection = None
    try:
        connection = handler.connection_factory()
        session, err = _require_super_admin(connection, handler)
        if err:
            status = 403 if session is not None or err == "Forbidden" else 401
            if err == "Forbidden":
                _write(handler, 403, {"error": "Forbidden"})
            else:
                _write(handler, 401, {"error": err})
            return True

        actor_id = session["user_id"]

        # ------------------------------------------------------------------ #
        # Tenant management
        # ------------------------------------------------------------------ #
        if method == "GET" and path == "/api/admin/tenants":
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, entra_tenant_id, display_label, enabled, created_at, updated_at"
                    " FROM core.tenant ORDER BY tenant_id"
                )
                cols = ["tenant_id", "entra_tenant_id", "display_label", "enabled", "created_at", "updated_at"]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            _write(handler, 200, {"tenants": rows})
            return True

        if method == "POST" and path == "/api/admin/tenants":
            body = _read_body(handler)
            entra_tenant_id = body.get("entra_tenant_id", "").strip()
            display_label = body.get("display_label", "").strip()
            enabled = body.get("enabled", True)
            if not entra_tenant_id or not display_label:
                _write(handler, 400, {"error": "entra_tenant_id and display_label are required"})
                return True
            with connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO core.tenant (entra_tenant_id, display_label, enabled)"
                    " VALUES (%s, %s, %s) RETURNING tenant_id, entra_tenant_id, display_label, enabled, created_at, updated_at",
                    (entra_tenant_id, display_label, enabled),
                )
                cols = ["tenant_id", "entra_tenant_id", "display_label", "enabled", "created_at", "updated_at"]
                tenant = dict(zip(cols, cur.fetchone()))
            _log_audit(connection, actor_id, "TENANT_CREATED", "tenant", tenant["tenant_id"],
                       before_state=None, after_state=tenant)
            connection.commit()
            _write(handler, 201, {"tenant": tenant})
            return True

        tenant_patch_prefix = "/api/admin/tenants/"
        if method == "PATCH" and path.startswith(tenant_patch_prefix):
            rest = path[len(tenant_patch_prefix):]
            # /api/admin/tenants/{id}/features/{flag_name}
            if "/features/" in rest:
                parts = rest.split("/features/", 1)
                tenant_id_str, flag_name = parts[0], parts[1]
                if not tenant_id_str.isdigit() or not flag_name:
                    _write(handler, 400, {"error": "Invalid tenant id or flag name"})
                    return True
                tenant_id = int(tenant_id_str)
                body = _read_body(handler)
                if "is_enabled" not in body:
                    _write(handler, 400, {"error": "is_enabled is required"})
                    return True
                is_enabled = bool(body["is_enabled"])
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT is_enabled FROM core.tenant_feature WHERE tenant_id = %s AND flag_name = %s",
                        (tenant_id, flag_name),
                    )
                    existing = cur.fetchone()
                    before = {"tenant_id": tenant_id, "flag_name": flag_name, "is_enabled": existing[0]} if existing else None
                    cur.execute(
                        """
                        INSERT INTO core.tenant_feature (tenant_id, flag_name, is_enabled)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (tenant_id, flag_name)
                        DO UPDATE SET is_enabled = EXCLUDED.is_enabled, updated_at = NOW()
                        RETURNING tenant_id, flag_name, is_enabled, updated_at
                        """,
                        (tenant_id, flag_name, is_enabled),
                    )
                    cols = ["tenant_id", "flag_name", "is_enabled", "updated_at"]
                    record = dict(zip(cols, cur.fetchone()))
                _log_audit(connection, actor_id, "FEATURE_FLAG_CHANGED", "tenant_feature",
                           f"{tenant_id}/{flag_name}", before_state=before, after_state=record)
                connection.commit()
                _write(handler, 200, {"tenant_feature": record})
                return True

            # /api/admin/tenants/{id}
            tenant_id_str = rest
            if not tenant_id_str.isdigit():
                _write(handler, 400, {"error": "Invalid tenant id"})
                return True
            tenant_id = int(tenant_id_str)
            body = _read_body(handler)
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, entra_tenant_id, display_label, enabled, created_at, updated_at"
                    " FROM core.tenant WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    _write(handler, 404, {"error": "Tenant not found"})
                    return True
                cols = ["tenant_id", "entra_tenant_id", "display_label", "enabled", "created_at", "updated_at"]
                before = dict(zip(cols, row))
                updates = []
                params = []
                if "display_label" in body:
                    updates.append("display_label = %s")
                    params.append(body["display_label"])
                if "enabled" in body:
                    updates.append("enabled = %s")
                    params.append(bool(body["enabled"]))
                if not updates:
                    _write(handler, 400, {"error": "No updatable fields provided"})
                    return True
                updates.append("updated_at = NOW()")
                params.append(tenant_id)
                cur.execute(
                    f"UPDATE core.tenant SET {', '.join(updates)} WHERE tenant_id = %s"
                    " RETURNING tenant_id, entra_tenant_id, display_label, enabled, created_at, updated_at",
                    params,
                )
                after = dict(zip(cols, cur.fetchone()))
            action = "TENANT_ENABLED" if after.get("enabled") else "TENANT_DISABLED"
            _log_audit(connection, actor_id, action, "tenant", tenant_id, before_state=before, after_state=after)
            connection.commit()
            _write(handler, 200, {"tenant": after})
            return True

        if method == "DELETE" and path.startswith(tenant_patch_prefix):
            tenant_id_str = path[len(tenant_patch_prefix):]
            if not tenant_id_str.isdigit():
                _write(handler, 400, {"error": "Invalid tenant id"})
                return True
            tenant_id = int(tenant_id_str)
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, entra_tenant_id, display_label, enabled, created_at, updated_at"
                    " FROM core.tenant WHERE tenant_id = %s",
                    (tenant_id,),
                )
                row = cur.fetchone()
                if not row:
                    _write(handler, 404, {"error": "Tenant not found"})
                    return True
                cols = ["tenant_id", "entra_tenant_id", "display_label", "enabled", "created_at", "updated_at"]
                before = dict(zip(cols, row))
                cur.execute(
                    "UPDATE core.tenant SET enabled = FALSE, updated_at = NOW() WHERE tenant_id = %s"
                    " RETURNING tenant_id, entra_tenant_id, display_label, enabled, created_at, updated_at",
                    (tenant_id,),
                )
                after = dict(zip(cols, cur.fetchone()))
            _log_audit(connection, actor_id, "TENANT_DISABLED", "tenant", tenant_id, before_state=before, after_state=after)
            connection.commit()
            _write(handler, 200, {"tenant": after})
            return True

        # ------------------------------------------------------------------ #
        # User management
        # ------------------------------------------------------------------ #
        if method == "GET" and path == "/api/admin/users":
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT user_id, email, role, tenant_id, is_active, totp_enrolled,"
                    " failed_login_attempts, locked_until, created_at, updated_at, last_login_at"
                    " FROM auth.\"user\" ORDER BY user_id"
                )
                cols = ["user_id", "email", "role", "tenant_id", "is_active", "totp_enrolled",
                        "failed_login_attempts", "locked_until", "created_at", "updated_at", "last_login_at"]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            _write(handler, 200, {"users": rows})
            return True

        if method == "POST" and path == "/api/admin/users":
            body = _read_body(handler)
            email = body.get("email", "").strip()
            password = body.get("password", "")
            role = body.get("role", "")
            tenant_id = body.get("tenant_id")
            if not email or not password or role not in ("SUPER_ADMIN", "TENANT_ADMIN", "TENANT_USER"):
                _write(handler, 400, {"error": "email, password, and valid role are required"})
                return True
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            with connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth.\"user\" (email, password_hash, role, tenant_id)"
                    " VALUES (%s, %s, %s, %s)"
                    " RETURNING user_id, email, role, tenant_id, is_active, totp_enrolled, created_at, updated_at",
                    (email, password_hash, role, tenant_id),
                )
                cols = ["user_id", "email", "role", "tenant_id", "is_active", "totp_enrolled", "created_at", "updated_at"]
                user = dict(zip(cols, cur.fetchone()))
            _log_audit(connection, actor_id, "USER_CREATED", "user", user["user_id"],
                       before_state=None, after_state={k: v for k, v in user.items()})
            connection.commit()
            _write(handler, 201, {"user": user})
            return True

        user_prefix = "/api/admin/users/"
        if path.startswith(user_prefix):
            rest = path[len(user_prefix):]

            if method == "POST" and rest.endswith("/reset-password"):
                user_id_str = rest[: -len("/reset-password")]
                if not user_id_str.isdigit():
                    _write(handler, 400, {"error": "Invalid user id"})
                    return True
                user_id = int(user_id_str)
                new_password = _generate_password()
                password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                with connection.cursor() as cur:
                    cur.execute(
                        "UPDATE auth.\"user\" SET password_hash = %s, updated_at = NOW() WHERE user_id = %s RETURNING user_id",
                        (password_hash, user_id),
                    )
                    if cur.fetchone() is None:
                        _write(handler, 404, {"error": "User not found"})
                        return True
                _log_audit(connection, actor_id, "PASSWORD_RESET", "user", user_id)
                connection.commit()
                _write(handler, 200, {"new_password": new_password})
                return True

            if method == "PATCH":
                user_id_str = rest
                if not user_id_str.isdigit():
                    _write(handler, 400, {"error": "Invalid user id"})
                    return True
                user_id = int(user_id_str)
                body = _read_body(handler)
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, email, role, tenant_id, is_active, totp_enrolled, created_at, updated_at"
                        " FROM auth.\"user\" WHERE user_id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        _write(handler, 404, {"error": "User not found"})
                        return True
                    cols = ["user_id", "email", "role", "tenant_id", "is_active", "totp_enrolled", "created_at", "updated_at"]
                    before = dict(zip(cols, row))
                    updates = []
                    params = []
                    if "role" in body:
                        updates.append("role = %s")
                        params.append(body["role"])
                    if "is_active" in body:
                        updates.append("is_active = %s")
                        params.append(bool(body["is_active"]))
                    if "tenant_id" in body:
                        updates.append("tenant_id = %s")
                        params.append(body["tenant_id"])
                    if not updates:
                        _write(handler, 400, {"error": "No updatable fields provided"})
                        return True
                    updates.append("updated_at = NOW()")
                    params.append(user_id)
                    cur.execute(
                        f"UPDATE auth.\"user\" SET {', '.join(updates)} WHERE user_id = %s"
                        " RETURNING user_id, email, role, tenant_id, is_active, totp_enrolled, created_at, updated_at",
                        params,
                    )
                    after = dict(zip(cols, cur.fetchone()))
                action = "USER_DISABLED" if not after.get("is_active") else "USER_ROLE_CHANGED"
                if "role" in body and body["role"] != before["role"]:
                    action = "USER_ROLE_CHANGED"
                elif not after.get("is_active") and before.get("is_active"):
                    action = "USER_DISABLED"
                _log_audit(connection, actor_id, action, "user", user_id, before_state=before, after_state=after)
                connection.commit()
                _write(handler, 200, {"user": after})
                return True

            if method == "DELETE":
                user_id_str = rest
                if not user_id_str.isdigit():
                    _write(handler, 400, {"error": "Invalid user id"})
                    return True
                user_id = int(user_id_str)
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, email, role, tenant_id, is_active, totp_enrolled, created_at, updated_at"
                        " FROM auth.\"user\" WHERE user_id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        _write(handler, 404, {"error": "User not found"})
                        return True
                    cols = ["user_id", "email", "role", "tenant_id", "is_active", "totp_enrolled", "created_at", "updated_at"]
                    before = dict(zip(cols, row))
                    cur.execute(
                        "UPDATE auth.\"user\" SET is_active = FALSE, updated_at = NOW() WHERE user_id = %s"
                        " RETURNING user_id, email, role, tenant_id, is_active, totp_enrolled, created_at, updated_at",
                        (user_id,),
                    )
                    after = dict(zip(cols, cur.fetchone()))
                _log_audit(connection, actor_id, "USER_DISABLED", "user", user_id, before_state=before, after_state=after)
                connection.commit()
                _write(handler, 200, {"user": after})
                return True

        # ------------------------------------------------------------------ #
        # Feature flags
        # ------------------------------------------------------------------ #
        if method == "GET" and path == "/api/admin/feature-flags":
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT flag_name, is_enabled, description, created_at, updated_at"
                    " FROM core.feature_flag ORDER BY flag_name"
                )
                flag_cols = ["flag_name", "is_enabled", "description", "created_at", "updated_at"]
                flags = {row[0]: dict(zip(flag_cols, row)) for row in cur.fetchall()}
                cur.execute(
                    "SELECT tenant_id, flag_name, is_enabled, updated_at FROM core.tenant_feature ORDER BY tenant_id, flag_name"
                )
                overrides: dict = {}
                for tenant_id, flag_name, is_enabled, updated_at in cur.fetchall():
                    overrides.setdefault(flag_name, []).append(
                        {"tenant_id": tenant_id, "is_enabled": is_enabled, "updated_at": updated_at}
                    )
            result = []
            for flag_name, flag in flags.items():
                result.append({**flag, "tenant_overrides": overrides.get(flag_name, [])})
            _write(handler, 200, {"feature_flags": result})
            return True

        flag_prefix = "/api/admin/feature-flags/"
        if method == "PATCH" and path.startswith(flag_prefix):
            flag_name = path[len(flag_prefix):]
            if not flag_name:
                _write(handler, 400, {"error": "flag_name is required"})
                return True
            body = _read_body(handler)
            if "is_enabled" not in body:
                _write(handler, 400, {"error": "is_enabled is required"})
                return True
            is_enabled = bool(body["is_enabled"])
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT flag_name, is_enabled, description, created_at, updated_at"
                    " FROM core.feature_flag WHERE flag_name = %s",
                    (flag_name,),
                )
                row = cur.fetchone()
                if not row:
                    _write(handler, 404, {"error": "Feature flag not found"})
                    return True
                cols = ["flag_name", "is_enabled", "description", "created_at", "updated_at"]
                before = dict(zip(cols, row))
                cur.execute(
                    "UPDATE core.feature_flag SET is_enabled = %s, updated_at = NOW() WHERE flag_name = %s"
                    " RETURNING flag_name, is_enabled, description, created_at, updated_at",
                    (is_enabled, flag_name),
                )
                after = dict(zip(cols, cur.fetchone()))
            _log_audit(connection, actor_id, "FEATURE_FLAG_CHANGED", "feature_flag", flag_name,
                       before_state=before, after_state=after)
            connection.commit()
            _write(handler, 200, {"feature_flag": after})
            return True

        # ------------------------------------------------------------------ #
        # System settings
        # ------------------------------------------------------------------ #
        if method == "GET" and path == "/api/admin/settings":
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT setting_key, setting_value, setting_type, description, updated_at, updated_by"
                    " FROM core.system_setting ORDER BY setting_key"
                )
                cols = ["setting_key", "setting_value", "setting_type", "description", "updated_at", "updated_by"]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            _write(handler, 200, {"settings": rows})
            return True

        settings_prefix = "/api/admin/settings/"
        if method == "PATCH" and path.startswith(settings_prefix):
            setting_key = path[len(settings_prefix):]
            if not setting_key:
                _write(handler, 400, {"error": "setting key is required"})
                return True
            body = _read_body(handler)
            if "setting_value" not in body:
                _write(handler, 400, {"error": "setting_value is required"})
                return True
            setting_value = str(body["setting_value"])
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT setting_key, setting_value, setting_type, description, updated_at, updated_by"
                    " FROM core.system_setting WHERE setting_key = %s",
                    (setting_key,),
                )
                row = cur.fetchone()
                if not row:
                    _write(handler, 404, {"error": "Setting not found"})
                    return True
                cols = ["setting_key", "setting_value", "setting_type", "description", "updated_at", "updated_by"]
                before = dict(zip(cols, row))
                cur.execute(
                    "UPDATE core.system_setting SET setting_value = %s, updated_at = NOW(), updated_by = %s"
                    " WHERE setting_key = %s"
                    " RETURNING setting_key, setting_value, setting_type, description, updated_at, updated_by",
                    (setting_value, actor_id, setting_key),
                )
                after = dict(zip(cols, cur.fetchone()))
            _log_audit(connection, actor_id, "SYSTEM_SETTING_CHANGED", "system_setting", setting_key,
                       before_state=before, after_state=after)
            connection.commit()
            _write(handler, 200, {"setting": after})
            return True

        # ------------------------------------------------------------------ #
        # Collector status
        # ------------------------------------------------------------------ #
        if method == "GET" and path == "/api/admin/collector/status":
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT collector_id, tenant_id, checkpoint_at, updated_at"
                    " FROM control.collector_checkpoint ORDER BY collector_id, tenant_id"
                )
                cols = ["collector_id", "tenant_id", "checkpoint_at", "updated_at"]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            _write(handler, 200, {"collector_status": rows})
            return True

        _write(handler, 404, {"error": "Not found"})
        return True

    except (ValueError, json.JSONDecodeError):
        _write(handler, 400, {"error": "Invalid request"})
        return True
    except Exception as exc:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        _write(handler, 503, {"error": str(exc)})
        return True
    finally:
        if connection is not None:
            connection.close()

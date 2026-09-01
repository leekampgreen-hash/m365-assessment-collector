BEGIN;
CREATE INDEX IF NOT EXISTS idx_session_user_id ON auth.session(user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires_at ON auth.session(expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_event_user_id ON auth.auth_event(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_event_occurred_at ON auth.auth_event(occurred_at);
CREATE INDEX IF NOT EXISTS idx_admin_audit_actor ON auth.admin_audit(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_occurred_at ON auth.admin_audit(occurred_at);
CREATE INDEX IF NOT EXISTS idx_api_access_log_occurred_at ON auth.api_access_log(occurred_at);
COMMIT;

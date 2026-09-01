BEGIN;

INSERT INTO core.feature_flag (flag_name, is_enabled, description) VALUES
('security_analyst', TRUE, 'Guided Security Analyst Agent'),
('license_optimizer', TRUE, 'License Optimizer with cost savings'),
('email_report', FALSE, 'Scheduled email reports'),
('cost_analysis', TRUE, 'SKU pricing and cost saving analysis'),
('sharepoint_sites', TRUE, 'SharePoint site usage panel'),
('mfa_coverage', TRUE, 'MFA coverage and registration panel'),
('admin_roles', TRUE, 'Admin role inventory panel'),
('ca_policies', TRUE, 'Conditional Access policy panel'),
('signin_analytics', TRUE, 'Sign-in logs and analytics panel')
ON CONFLICT (flag_name) DO NOTHING;

INSERT INTO core.system_setting (setting_key, setting_value, setting_type, description) VALUES
('session_ttl_minutes', '60', 'INTEGER', 'Session timeout in minutes'),
('max_login_attempts', '5', 'INTEGER', 'Failed login attempts before lockout'),
('lockout_duration_minutes', '30', 'INTEGER', 'Account lockout duration in minutes'),
('totp_window', '1', 'INTEGER', 'TOTP tolerance window (number of 30s steps)'),
('session_extend_on_activity', 'true', 'BOOLEAN', 'Reset session TTL on each request'),
('api_access_log_enabled', 'true', 'BOOLEAN', 'Log all API access'),
('admin_audit_enabled', 'true', 'BOOLEAN', 'Log all admin actions'),
('password_min_length', '12', 'INTEGER', 'Minimum password length'),
('totp_issuer', 'm365-assessment', 'STRING', 'TOTP issuer name shown in authenticator app')
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO auth."user" (email, password_hash, totp_secret, totp_enrolled, role, tenant_id, is_active)
VALUES ('admin@localhost', '$2b$12$9/3BShBEYatfqWi8q6Uo4umQm3oqC2MWhTdC93HNg3JhGdTjxfni.', 'LPRTYQKIIKNQ5XXZTCYMK473VU3AMJVG', FALSE, 'SUPER_ADMIN', NULL, TRUE)
ON CONFLICT (email) DO NOTHING;

COMMIT;

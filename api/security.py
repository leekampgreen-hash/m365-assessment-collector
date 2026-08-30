"""Read-only query service and HTTP helpers for persisted Security findings.

This module is deliberately an API adapter over the persisted deterministic
projection. It does not evaluate rules, call Graph, or write to PostgreSQL.
"""
from __future__ import annotations

from typing import Any, Mapping


VALID_STATUSES = ("OPEN", "PASS", "NOT_EVALUATED")
VALID_SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")


class SecurityFindingQueryService:
    """Bounded reads over the current finding projection and its evidence."""

    def __init__(self, connection: Any, tenant_id: int):
        self.connection = connection
        self.tenant_id = tenant_id

    def _fetchall(self, query: str, parameters: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        cursor = self.connection.cursor()
        cursor.execute(query, parameters)
        return list(cursor.fetchall())

    def _fetchone(self, query: str, parameters: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
        cursor = self.connection.cursor()
        cursor.execute(query, parameters)
        return cursor.fetchone()

    @classmethod
    def from_connection(cls, connection: Any, tenant_id: int) -> "SecurityFindingQueryService":
        return cls(connection, tenant_id)

    @staticmethod
    def _finding(row: tuple[Any, ...]) -> dict[str, Any]:
        names = (
            "finding_id", "rule_id", "category", "title", "status", "severity",
            "baseline_id", "baseline_version", "baseline_expectation", "observed_state",
            "risk", "recommendation", "validation_guidance", "dependency_status", "evaluated_at",
        )
        return dict(zip(names, row))

    def findings(self, *, status: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
        clauses = ["c.tenant_id = %s"]
        parameters: list[Any] = [self.tenant_id]
        if status is not None:
            clauses.append("c.status = %s")
            parameters.append(status)
        if severity is not None:
            clauses.append("c.severity = %s")
            parameters.append(severity)
        query = """SELECT c.finding_id, e.rule_id, e.category, e.category,
                          c.status, c.severity, c.baseline_id, c.baseline_version,
                          e.baseline_expectation, c.observed_state, e.risk,
                          e.recommendation, e.validation_guidance, e.dependency_status,
                          c.evaluated_at
                   FROM security.finding_current c
                   JOIN security.finding_evaluation e
                     ON e.evaluation_id = c.latest_evaluation_id
                    AND e.tenant_id = c.tenant_id
                   WHERE """ + " AND ".join(clauses) + " ORDER BY c.evaluated_at DESC, c.finding_id"
        return [self._finding(row) for row in self._fetchall(query, tuple(parameters))]

    def summary(self) -> dict[str, Any]:
        row = self._fetchone(
            """SELECT count(*)::int,
                      count(*) FILTER (WHERE status = 'OPEN')::int,
                      count(*) FILTER (WHERE status = 'PASS')::int,
                      count(*) FILTER (WHERE status = 'NOT_EVALUATED')::int,
                      max(evaluated_at)
               FROM security.finding_current WHERE tenant_id = %s""",
            (self.tenant_id,),
        ) or (0, 0, 0, 0, None)
        severity_rows = self._fetchall(
            """SELECT severity, count(*)::int FROM security.finding_current
               WHERE tenant_id = %s AND status = 'OPEN' GROUP BY severity ORDER BY severity""",
            (self.tenant_id,),
        )
        return {
            "total_findings": row[0],
            "status_counts": {"OPEN": row[1], "PASS": row[2], "NOT_EVALUATED": row[3]},
            "open_severity_distribution": {item[0]: item[1] for item in severity_rows},
            "latest_evaluated_at": row[4],
        }

    def detail(self, finding_id: str) -> dict[str, Any] | None:
        rows = self._fetchall(
            """SELECT c.finding_id, e.rule_id, e.category, e.category,
                      c.status, c.severity, c.baseline_id, c.baseline_version,
                      e.baseline_expectation, c.observed_state, e.risk,
                      e.recommendation, e.validation_guidance, e.dependency_status,
                      c.evaluated_at, o.source_type, o.source_endpoint,
                      o.normalized_field, o.normalized_value, o.observed_at,
                      o.collection_run_id, o.endpoint_run_id
               FROM security.finding_current c
               JOIN security.finding_evaluation e
                 ON e.evaluation_id = c.latest_evaluation_id AND e.tenant_id = c.tenant_id
               JOIN security.observation o
                 ON o.observation_id = e.observation_id AND o.tenant_id = c.tenant_id
               WHERE c.tenant_id = %s AND c.finding_id = %s""",
            (self.tenant_id, finding_id),
        )
        if not rows:
            return None
        finding = self._finding(rows[0][:15])
        finding["evidence"] = {
            "source_type": rows[0][15],
            "source_endpoint": rows[0][16],
            "normalized_field": rows[0][17],
            "normalized_value": rows[0][18],
            "observed_at": rows[0][19],
            "collection_run_id": rows[0][20],
            "endpoint_run_id": rows[0][21],
        }
        return finding

    def signin_risk(self) -> dict[str, Any]:
        row = self._fetchone(
            """SELECT count(*) FILTER (WHERE COALESCE(is_deleted, false) = false)::int,
                      count(*) FILTER (WHERE COALESCE(is_deleted, false) = false AND upper(risk_level) = 'HIGH')::int,
                      count(*) FILTER (WHERE COALESCE(is_deleted, false) = false AND upper(risk_level) = 'MEDIUM')::int,
                      count(*) FILTER (WHERE COALESCE(is_deleted, false) = false AND upper(risk_level) = 'LOW')::int
               FROM core.risky_user WHERE tenant_id = %s""",
            (self.tenant_id,),
        ) or (0, 0, 0, 0)
        detection_row = self._fetchone(
            """SELECT count(*)::int,
                      count(*) FILTER (WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '30 days')::int
               FROM core.risk_detection WHERE tenant_id = %s""",
            (self.tenant_id,),
        ) or (0, 0)
        return {
            "risky_users": {"total": row[0], "high_risk": row[1], "medium_risk": row[2], "low_risk": row[3]},
            "risk_detections": {"total": detection_row[0], "recent_30d": detection_row[1]},
        }

    def mfa_registration(self) -> dict[str, Any]:
        rows = self._fetchall(
            """SELECT u.display_name, COALESCE((r.payload ->> 'isMfaRegistered')::boolean, false),
                      EXISTS (SELECT 1 FROM core.directory_role_assignment a
                              WHERE a.tenant_id = u.tenant_id AND a.principal_id = u.source_object_id)
               FROM core.\"user\" u
               LEFT JOIN LATERAL (
                   SELECT payload FROM raw.raw_graph_record
                   WHERE tenant_id = u.tenant_id AND endpoint_id = 'G01-021'
                     AND (source_object_id = u.source_object_id OR payload ->> 'id' = u.source_object_id
                          OR lower(payload ->> 'userPrincipalName') = lower(u.user_principal_name))
                   ORDER BY collected_at DESC LIMIT 1
               ) r ON true
               WHERE u.tenant_id = %s AND u.account_enabled IS TRUE
                 AND r.payload IS NOT NULL
               ORDER BY u.display_name NULLS LAST""",
            (self.tenant_id,),
        )
        aggregate = self._fetchone(
            """SELECT normalized_value::jsonb FROM security.observation
               WHERE tenant_id = %s AND rule_id = 'M365-ENTRA-MFA-REG-001'
               ORDER BY observed_at DESC LIMIT 1""", (self.tenant_id,))
        if rows:
            total = len(rows)
            registered = sum(bool(row[1]) for row in rows)
            without = [{"display_name": row[0] or "Unknown", "is_admin": bool(row[2])}
                       for row in rows if not row[1]]
            admin_gap = any(item["is_admin"] for item in without)
        else:
            value = (aggregate or ({},))[0] or {}
            total = int(value.get("enabled_user_count", 0))
            registered = int(value.get("mfa_registered_count", 0))
            without = []
            admin_gap = False
        not_registered = total - registered
        rate = round(registered / total * 100, 2) if total else 100.0
        findings = []
        if rate < 80:
            findings.append({"finding": f"Only {rate}% of users have MFA registered", "risk": "HIGH"})
        if admin_gap or self._fetchone(
            "SELECT 1 FROM security.finding_current WHERE tenant_id = %s AND rule_id = 'M365-ENTRA-ADMIN-MFA-REG-001' AND status = 'OPEN' LIMIT 1",
            (self.tenant_id,),
        ):
            findings.append({"finding": "Administrator without MFA detected", "risk": "HIGH"})
        if rate < 95:
            findings.append({"finding": f"{not_registered} users without MFA", "risk": "MEDIUM"})
        return {"total_users": total, "mfa_registered": registered, "mfa_not_registered": not_registered,
                "registration_rate_pct": rate, "users_without_mfa": without, "findings": findings}

    def signin_detail(self) -> dict[str, Any]:
        rows = self._fetchall(
            """SELECT COALESCE(l.user_display_name, u.display_name, 'Unknown'),
                      count(*)::int,
                      count(*) FILTER (WHERE l.status_error_code <> 0 OR l.status_failure_reason IS NOT NULL)::int,
                      COALESCE(array_agg(DISTINCT l.location_country) FILTER (WHERE l.location_country IS NOT NULL AND l.location_country <> ''), ARRAY[]::text[]),
                      count(*) FILTER (WHERE lower(COALESCE(l.client_app_used, '')) LIKE ANY (ARRAY['%%legacy%%', '%%imap%%', '%%pop%%', '%%smtp%%', '%%basic%%']))::int,
                      max(l.signin_datetime),
                      u.source_object_id
               FROM core.signin_log l
               LEFT JOIN core.\"user\" u ON u.tenant_id = l.tenant_id
                 AND lower(u.user_principal_name) = lower(l.user_principal_name)
               WHERE l.tenant_id = %s AND l.signin_datetime >= CURRENT_TIMESTAMP - INTERVAL '30 days'
               GROUP BY COALESCE(l.user_display_name, u.display_name, 'Unknown'), u.source_object_id
               ORDER BY count(*) FILTER (WHERE l.status_error_code <> 0 OR l.status_failure_reason IS NOT NULL) DESC,
                        count(*) DESC LIMIT 20""", (self.tenant_id,))
        risky = {row[0] for row in self._fetchall(
            "SELECT source_object_id FROM core.risky_user WHERE tenant_id = %s AND COALESCE(is_deleted, false) = false", (self.tenant_id,))}
        users = []
        for name, total, failed, countries, legacy, last, object_id in rows:
            countries = sorted(str(country) for country in (countries or []))
            rate = round(failed / total * 100, 2) if total else 0.0
            signals = []
            if rate > 30: signals.append("High failure rate")
            if legacy > 0: signals.append("Uses legacy authentication")
            if len(countries) > 2: signals.append("Signs in from multiple countries")
            if object_id in risky: signals.append("Flagged as risky by Entra")
            users.append({"display_name": name or "Unknown", "total_signins": total, "failed_signins": failed,
                          "failure_rate_pct": rate, "countries": countries, "legacy_auth_count": legacy,
                          "last_signin": last, "risk_signals": signals})
        return {"period_days": 30, "total_users_with_activity": len(users), "users": users}

    def risk_score(self) -> dict[str, Any]:
        detail = self.signin_detail()
        signin = {item["display_name"]: item for item in detail["users"]}
        users = self._fetchall("SELECT source_object_id, display_name FROM core.\"user\" WHERE tenant_id = %s AND account_enabled IS TRUE", (self.tenant_id,))
        risky = {row[0] for row in self._fetchall("SELECT source_object_id FROM core.risky_user WHERE tenant_id = %s AND COALESCE(is_deleted, false) = false", (self.tenant_id,))}
        mfa_open = bool(self._fetchone("SELECT 1 FROM security.finding_current WHERE tenant_id = %s AND rule_id ILIKE '%%MFA%%' AND status = 'OPEN' LIMIT 1", (self.tenant_id,)))
        admin_ids = {row[0] for row in self._fetchall("SELECT DISTINCT principal_id FROM core.directory_role_assignment WHERE tenant_id = %s", (self.tenant_id,))}
        ca_weak = bool(self._fetchone("SELECT 1 FROM core.conditional_access_policy WHERE tenant_id = %s AND state = 'enabledForReportingButNotEnforced' LIMIT 1", (self.tenant_id,)))
        tenant_risks = ["Conditional Access policies are in report-only mode"] if ca_weak else []
        scored = []
        for object_id, name in users:
            item = signin.get(name or "Unknown", {})
            score, factors = (20 if ca_weak else 0), (["Conditional Access policy not enforced"] if ca_weak else [])
            if mfa_open:
                score += 40; factors.append("MFA is not registered")
            if object_id in admin_ids and mfa_open:
                score += 30; factors.append("Administrator without MFA")
            if object_id in risky:
                score += 50; factors.append("Flagged as risky by Entra")
            if item.get("failure_rate_pct", 0) > 30:
                score += 30; factors.append("High sign-in failure rate")
            if len(item.get("countries", [])) > 2:
                score += 20; factors.append("Signs in from multiple countries")
            level = "CRITICAL" if score >= 81 else "HIGH" if score >= 51 else "MEDIUM" if score >= 21 else "LOW"
            scored.append({"display_name": name or "Unknown", "risk_level": level, "score": score, "risk_factors": factors})
        scored.sort(key=lambda item: item["score"], reverse=True)
        distribution = {level: sum(item["risk_level"] == level for item in scored) for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
        return {"scoring_model_version": "1.0", "total_users_scored": len(scored), "risk_distribution": distribution,
                "top_risks": scored[:10], "tenant_wide_risks": tenant_risks}

    def mfa_coverage(self) -> dict[str, Any]:
        rows = self._fetchall(
            """SELECT rule_id, status, count(*)::int
               FROM security.finding_current
               WHERE tenant_id = %s AND rule_id ILIKE '%%MFA%%'
               GROUP BY rule_id, status ORDER BY rule_id, status""",
            (self.tenant_id,),
        )
        findings = [{"rule_id": row[0], "status": row[1], "count": row[2]} for row in rows]
        total = sum(row[2] for row in rows)
        passed = sum(row[2] for row in rows if row[1] == "PASS")
        return {"findings": findings, "mfa_pass_rate": passed / total if total else None}

    def ca_policies(self) -> dict[str, Any]:
        rows = self._fetchall(
            """SELECT display_name, state
               FROM core.conditional_access_policy
               WHERE tenant_id = %s ORDER BY display_name NULLS LAST""",
            (self.tenant_id,),
        )
        disabled = sum(1 for row in rows if str(row[1]).upper() == "DISABLED")
        enabled = len(rows) - disabled
        return {
            "total": len(rows),
            "enabled": enabled,
            "disabled": disabled,
            "policies": [{"display_name": row[0], "state": row[1]} for row in rows],
        }

    def admin_roles(self) -> dict[str, Any]:
        rows = self._fetchall(
            """SELECT d.display_name, d.description, COUNT(a.principal_id)::int
               FROM core.directory_role_definition d
               JOIN core.directory_role_assignment a
                 ON a.role_definition_id = d.source_object_id
                AND a.tenant_id = d.tenant_id
               WHERE d.tenant_id = %s
               GROUP BY d.display_name, d.description
               ORDER BY COUNT(a.principal_id) DESC""",
            (self.tenant_id,),
        )
        privileged_roles = {
            "exchange administrator", "sharepoint administrator", "security administrator",
            "compliance administrator", "user administrator", "billing administrator",
        }
        roles = []
        for name, description, assigned_users in rows:
            role_name = str(name or "")
            count = int(assigned_users or 0)
            normalized_name = role_name.casefold()
            if normalized_name == "global administrator" or count > 3:
                risk_level = "HIGH"
            elif normalized_name in privileged_roles:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            roles.append({
                "role_name": name,
                "role_description": description,
                "assigned_users": count,
                "risk_level": risk_level,
            })
        global_count = next((role["assigned_users"] for role in roles if str(role["role_name"]).casefold() == "global administrator"), 0)
        findings = []
        if global_count > 3:
            findings.append({"finding": f"Too many Global Administrators ({global_count}) — recommend maximum 3", "risk": "HIGH"})
        findings.extend(
            {"finding": f"{role['role_name']} has {role['assigned_users']} assignments — review necessity", "risk": "HIGH"}
            for role in roles
            if role["risk_level"] == "HIGH" and role["assigned_users"] > 5
        )
        return {
            "total_roles_assigned": len(roles),
            "high_privilege_roles": sum(1 for role in roles if role["risk_level"] == "HIGH"),
            "roles": roles,
            "findings": findings,
        }

    def data_quality(self) -> dict[str, Any]:
        row = self._fetchone(
            """SELECT count(*)::int,
                      count(*) FILTER (WHERE status = 'NOT_EVALUATED')::int,
                      count(DISTINCT rule_id)::int, max(evaluated_at)
               FROM security.finding_current WHERE tenant_id = %s""",
            (self.tenant_id,),
        ) or (0, 0, 0, None)
        baselines = self._fetchall(
            """SELECT DISTINCT baseline_id, baseline_version FROM security.finding_current
               WHERE tenant_id = %s ORDER BY baseline_id, baseline_version""",
            (self.tenant_id,),
        )
        observations = self._fetchone(
            """SELECT EXISTS (SELECT 1 FROM security.observation WHERE tenant_id = %s)""",
            (self.tenant_id,),
        )
        return {
            "deterministic_engine_status": "READY",
            "persisted_observation_available": bool(observations and observations[0]),
            "latest_evaluation_timestamp": row[3],
            "not_evaluated_count": row[1],
            "current_rule_count": row[2],
            "current_baselines": [{"baseline_id": item[0], "version": item[1]} for item in baselines],
            "known_source_limitations": ["Security findings reflect persisted collector observations only."],
        }


def validate_filters(status: str | None, severity: str | None) -> str | None:
    if status is not None and status not in VALID_STATUSES:
        return "INVALID_STATUS_FILTER"
    if severity is not None and severity not in VALID_SEVERITIES:
        return "INVALID_SEVERITY_FILTER"
    return None


__all__ = ["SecurityFindingQueryService", "VALID_STATUSES", "VALID_SEVERITIES", "validate_filters"]

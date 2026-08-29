"""Deterministic security baseline rules."""
from __future__ import annotations

from security.rules.sp_ext_001 import (
    BASELINE_VALUE,
    EXTERNAL_SHARING_LEVELS,
    RULE_CATEGORY,
    RULE_ID,
    evaluate_external_sharing,
    external_sharing_rule,
)
from security.rules.entra_guest_001 import (
    BASELINE_VALUE as GUEST_BASELINE_VALUE,
    GUEST_INVITATION_LEVELS,
    RULE_ID as GUEST_RULE_ID,
    evaluate_guest_invitation,
    guest_invitation_rule,
)
from security.rules.entra_consent_001 import (
    CONSENT_STATES,
    RULE_CATEGORY as CONSENT_RULE_CATEGORY,
    RULE_ID as CONSENT_RULE_ID,
    evaluate_user_consent,
    user_consent_rule,
)
from security.rules.entra_risky_consent_001 import (
    BASELINE_VALUE as RISKY_CONSENT_BASELINE_VALUE,
    DEPENDENCY_UNAVAILABLE as RISKY_CONSENT_DEPENDENCY_UNAVAILABLE,
    DISABLED_STATE as RISKY_CONSENT_DISABLED_STATE,
    ENABLED_STATE as RISKY_CONSENT_ENABLED_STATE,
    RULE_CATEGORY as RISKY_CONSENT_RULE_CATEGORY,
    RULE_ID as RISKY_CONSENT_RULE_ID,
    evaluate_risky_consent,
    risky_consent_rule,
)

__all__ = [
    "BASELINE_VALUE",
    "EXTERNAL_SHARING_LEVELS",
    "RULE_CATEGORY",
    "RULE_ID",
    "evaluate_external_sharing",
    "external_sharing_rule",
    "GUEST_BASELINE_VALUE",
    "GUEST_INVITATION_LEVELS",
    "GUEST_RULE_ID",
    "evaluate_guest_invitation",
    "guest_invitation_rule",
    "CONSENT_STATES",
    "CONSENT_RULE_CATEGORY",
    "CONSENT_RULE_ID",
    "evaluate_user_consent",
    "user_consent_rule",
    "RISKY_CONSENT_BASELINE_VALUE",
    "RISKY_CONSENT_DEPENDENCY_UNAVAILABLE",
    "RISKY_CONSENT_DISABLED_STATE",
    "RISKY_CONSENT_ENABLED_STATE",
    "RISKY_CONSENT_RULE_CATEGORY",
    "RISKY_CONSENT_RULE_ID",
    "evaluate_risky_consent",
    "risky_consent_rule",
]

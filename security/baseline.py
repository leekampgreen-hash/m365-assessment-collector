"""Product baseline definition for Security Findings.

The baseline id is ``m365-security-recommended-v1`` with an explicit version.

This is a PRODUCT baseline.  It does NOT claim CIS compliance, NIST
certification, Microsoft Secure Score equivalence, or any regulatory
certification.  ``formal_compliance_claim`` is ``False``.
"""
from __future__ import annotations

from security.models import SecurityBaseline

#: Explicit, semantic version of this product baseline.
BASELINE_VERSION = "1.0.0"

#: Product baseline identifier required by the CH8 contract.
BASELINE_ID = "m365-security-recommended-v1"


def recommended_baseline() -> SecurityBaseline:
    """Return the frozen product baseline object."""
    return SecurityBaseline(
        baseline_id=BASELINE_ID,
        version=BASELINE_VERSION,
        display_name="M365 Security Recommended Baseline",
        description=(
            "Product-level recommended baseline for the Microsoft 365 Security "
            "& Operational Intelligence product. It is a product baseline and "
            "does not claim CIS, NIST, Microsoft Secure Score, or regulatory "
            "compliance."
        ),
        formal_compliance_claim=False,
    )


__all__ = [
    "BASELINE_ID",
    "BASELINE_VERSION",
    "recommended_baseline",
]

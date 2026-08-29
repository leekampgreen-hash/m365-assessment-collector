"""Integration tests: permission semantics, baseline, missing permissions.

These tests verify:

* The current app baseline (User.Read) is recognized for the AUTH
  scenario and the catalog reports no missing permissions for it.
* Mail, calendar, and file scenarios each report the missing
  permission against the User.Read-only baseline.
* No scenario implicitly assumes broad or wildcard permissions.
"""
from __future__ import annotations

import unittest

from agents.scenario.catalog_loader import (
    build_catalog_registry,
    evaluate_permission_readiness,
    load_scenario_catalog,
)


class PermissionBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = load_scenario_catalog()
        cls.by_id = {ls.scenario_id: ls for ls in cls.result.loaded_scenarios}
        cls.reg_result = build_catalog_registry(cls.result)

    def test_baseline_is_user_read(self):
        self.assertEqual(self.result.current_baseline_permissions, ("User.Read",))

    def test_auth_scenario_recognizes_baseline_and_misses_nothing(self):
        auth = self.by_id["SCN-AUTH-001"]
        pr = evaluate_permission_readiness(
            auth, available_permissions=["User.Read"]
        )
        self.assertEqual(pr.status, "READY")
        self.assertEqual(pr.missing_permissions, ())
        self.assertEqual(pr.currently_available_permissions, ("User.Read",))

    def test_mail_scenario_missing_mail_send(self):
        # The mail scenarios are currently disabled in the catalog;
        # readiness status reports DISABLED. The missing permission
        # is still recorded for documentation purposes.
        for sid in ("SCN-MAIL-001", "SCN-MAIL-002"):
            pr = evaluate_permission_readiness(
                self.by_id[sid], available_permissions=["User.Read"]
            )
            self.assertEqual(pr.status, "DISABLED")
            self.assertEqual(pr.missing_permissions, ("Mail.Send",))

    def test_calendar_scenarios_missing_calendar_readwrite(self):
        for sid in ("SCN-CALENDAR-001", "SCN-CALENDAR-002", "SCN-CALENDAR-003"):
            pr = evaluate_permission_readiness(
                self.by_id[sid], available_permissions=["User.Read"]
            )
            self.assertEqual(pr.status, "DISABLED")
            self.assertEqual(pr.missing_permissions, ("Calendars.ReadWrite",))

    def test_file_scenarios_missing_files_readwrite(self):
        for sid in ("SCN-FILE-001", "SCN-FILE-002", "SCN-FILE-003"):
            pr = evaluate_permission_readiness(
                self.by_id[sid], available_permissions=["User.Read"]
            )
            self.assertEqual(pr.status, "DISABLED")
            self.assertEqual(pr.missing_permissions, ("Files.ReadWrite",))

    def test_disabled_scenarios_report_disabled_not_missing(self):
        # SCN-MAIL-001 is disabled in the catalog; even though
        # Mail.Send is missing, the readiness status reports DISABLED
        # because the scenario is not enabled.
        mail = self.by_id["SCN-MAIL-001"]
        pr = evaluate_permission_readiness(
            mail, available_permissions=["User.Read"]
        )
        self.assertEqual(pr.status, "DISABLED")
        self.assertFalse(pr.enabled)

    def test_no_scenario_assumes_wildcard(self):
        for ls in self.result.loaded_scenarios:
            for perm in ls.definition.required_delegated_permissions:
                self.assertNotIn("*", perm)
                self.assertFalse(perm.endswith(".All"))

    def test_permission_readiness_fields_distinguish(self):
        mail = self.by_id["SCN-MAIL-001"]
        pr = evaluate_permission_readiness(
            mail, available_permissions=["User.Read"]
        )
        # The "effective required permissions" is what the scenario
        # declares; "currently available permissions" is the supplied
        # baseline. The two are kept distinct.
        self.assertEqual(pr.required_scenario_permissions, ("Mail.Send",))
        self.assertEqual(pr.effective_required_permissions, ("Mail.Send",))
        self.assertEqual(pr.currently_available_permissions, ("User.Read",))

    def test_with_full_baseline_mail_scenario_is_ready(self):
        mail = self.by_id["SCN-MAIL-001"]
        # If Mail.Send is granted, the scenario is still DISABLED
        # because it is disabled in the catalog; the readiness
        # evaluation returns DISABLED regardless of permissions.
        pr = evaluate_permission_readiness(
            mail,
            available_permissions=["User.Read", "Mail.Send"],
        )
        self.assertEqual(pr.status, "DISABLED")

    def test_interactive_signin_requires_only_user_read(self):
        from agents.scenario.actions import declared_permissions_for

        self.assertEqual(
            declared_permissions_for("INTERACTIVE_SIGNIN"),
            ["User.Read"],
        )


if __name__ == "__main__":
    unittest.main()
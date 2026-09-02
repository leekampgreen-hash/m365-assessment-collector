import unittest
from datetime import datetime, timezone
from collectors.batch2 import SOURCES, aggregate_records, normalize_record


class Batch2Tests(unittest.TestCase):
    def test_alert_normalization(self):
        row = normalize_record("defender_alerts", {"id": "a1", "title": "Alert", "status": "new", "severity": "high"}, 2, datetime.now(timezone.utc))
        self.assertEqual(row["source_id"], "a1")
        self.assertEqual(row["name"], "Alert")
        self.assertEqual(row["severity"], "high")

    def test_policy_normalization(self):
        row = normalize_record("dlp_policies", {"id": "p1", "name": "Policy", "state": "enabled"}, 2, datetime.now(timezone.utc))
        self.assertEqual(row["source_id"], "p1")
        self.assertEqual(row["status"], "enabled")


if __name__ == "__main__":
    unittest.main()

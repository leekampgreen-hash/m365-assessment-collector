from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from collectors.persistence import open_database_connection

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class CollectionScheduler:
    def __init__(self, config_path: str = "config/scheduler.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        settings = self.config.get("settings", {})
        self.scheduler = BlockingScheduler(timezone=settings.get("timezone", "UTC"))

    def _load_config(self, path: str) -> dict:
        with Path(path).open() as config_file:
            return json.load(config_file)

    def _run_command(self, label: str, args: list[str], permissions: list[str]) -> None:
        try:
            command = [sys.executable, "-m", "collectors.run_collector", *args]
            if permissions:
                command += ["--granted-graph-permissions", *permissions]
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info("%s completed", label)
            else:
                logger.error("%s failed: %s", label, result.stderr[:200])
        except Exception as exc:
            logger.error("%s error: %s", label, exc)

    def _cleanup_old_events(self) -> None:
        connection = None
        try:
            connection = open_database_connection()
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM core.signin_log WHERE tenant_id = %s AND observed_at < NOW() - INTERVAL '90 days'", (2,))
                deleted = cursor.rowcount
            connection.commit()
            logger.info("Event cleanup complete — deleted %s rows", deleted)
        except Exception as exc:
            logger.error("Event cleanup failed: %s", exc)
            if connection is not None:
                connection.rollback()
        finally:
            if connection is not None:
                connection.close()

    def _run_endpoints(self, schedule: dict) -> None:
        name = schedule["name"]
        logger.info("Running phase %s schedule: %s", schedule.get("phase", 1), name)
        if schedule.get("data_type") == "maintenance":
            self._cleanup_old_events()
            return
        permissions = schedule.get("granted_permissions", [])
        for endpoint_id in schedule.get("endpoints", []):
            self._run_command(f"Endpoint {endpoint_id}", ["--endpoint", endpoint_id], permissions)
        for rule_id in schedule.get("security_rules", []):
            self._run_command(f"Rule {rule_id}", ["--security-rule", rule_id], permissions)
        if schedule.get("special") == "usage_reports":
            self._run_command("Usage reports", ["--all"], permissions)
        if schedule.get("special") == "sharepoint_audit":
            self._run_command("SharePoint audit", ["--sharepoint-audit"], permissions)
        if schedule.get("special") == "sharepoint_sites":
            self._run_command("SharePoint sites", ["--sharepoint-sites"], permissions)
        logger.info("Schedule %s complete", name)

    def _run_initial_phases(self) -> None:
        schedules = [s for s in self.config.get("schedules", []) if s.get("enabled", True)]
        for schedule in sorted((s for s in schedules if s.get("phase", 1) == 1), key=lambda s: s["name"]):
            self._run_endpoints(schedule)
        logger.info("Phase 1 complete — starting Phase 2 security evaluation")
        for schedule in sorted((s for s in schedules if s.get("phase") == 2), key=lambda s: s["name"]):
            self._run_endpoints(schedule)
        logger.info("Phase 2 complete — security findings updated")
        for schedule in sorted((s for s in schedules if s.get("phase") == 3), key=lambda s: s["name"]):
            self._run_endpoints(schedule)

    def register_jobs(self) -> None:
        for schedule in self.config.get("schedules", []):
            if not schedule.get("enabled", True):
                continue
            interval_hours = schedule.get("interval_hours", 24)
            self.scheduler.add_job(
                self._run_endpoints,
                trigger=IntervalTrigger(hours=interval_hours),
                args=[schedule], id=schedule["name"], name=schedule["description"],
                max_instances=1, coalesce=True, misfire_grace_time=3600,
                next_run_time=None,
            )
            logger.info("Registered job: %s every %sh", schedule["name"], interval_hours)

    def start(self) -> None:
        delay = self.config.get("settings", {}).get("startup_delay_seconds", 30)
        logger.info("Scheduler starting — waiting %ss before first run", delay)
        time.sleep(delay)
        try:
            self._run_initial_phases()
        except Exception as exc:
            logger.error("Initial phased collection failed: %s", exc)
        self.register_jobs()
        logger.info("Scheduler started — running jobs on schedule")
        try:
            self.scheduler.start()
        except Exception:
            logger.exception("Scheduler stopped unexpectedly")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    CollectionScheduler().start()


if __name__ == "__main__":
    main()

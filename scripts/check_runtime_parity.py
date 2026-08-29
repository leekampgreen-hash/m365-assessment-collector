from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

MODULES = (
    "analytics/operations.py",
    "collectors/usage_reports/registry.py",
    "api/operations.py",
    "collectors/persistence/core.py",
    "collectors/core/runtime.py",
)


def digest(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("container", nargs="?", default="graph-agent-operations-api-dev")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected = {module: digest(root / module) for module in MODULES}
    result = subprocess.run(
        ["docker", "exec", args.container, "md5sum", *(f"/workspace/{module}" for module in MODULES)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print(result.stderr.strip() or "runtime parity inspection failed", file=sys.stderr)
        return result.returncode
    actual = {}
    for line in result.stdout.splitlines():
        value, path = line.split(None, 1)
        actual[path.removeprefix("/workspace/")] = value
    failed = False
    for module in MODULES:
        match = expected[module] == actual.get(module)
        print(f"{module}: {'MATCH' if match else 'MISMATCH'} host={expected[module]} runtime={actual.get(module, 'MISSING')}")
        failed |= not match
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())

"""Backward-compatible shortcut; prefer: python main.py groups"""

from main import main
import sys


if __name__ == "__main__":
    sys.argv[1:] = ["groups", *sys.argv[1:]]
    raise SystemExit(main())

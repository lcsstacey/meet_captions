"""Backwards-compatible entry point: `python script.py` still works."""

from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())

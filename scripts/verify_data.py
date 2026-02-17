#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.reset_demo import db_path, run_integrity_checks


def main() -> None:
    path = db_path()
    if not Path(path).exists():
        raise SystemExit(f"Database not found at {path}. Run reset_demo.py first.")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_integrity_checks(conn)
    finally:
        conn.close()

    print("Integrity checks passed.")


if __name__ == "__main__":
    main()

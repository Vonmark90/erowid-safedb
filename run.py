#!/usr/bin/env python3
"""
Convenience launcher for Erowid SafeDB.
Usage:
    python3 run.py init
    python3 run.py web --port 8080
    python3 run.py check-combo alcohol xanax
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erowid_safedb.cli import main

if __name__ == "__main__":
    main()

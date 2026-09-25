#!/usr/bin/env bash
# Double-click this script from macOS Finder to launch Erowid SafeDB Desktop GUI
cd "$(dirname "$0")"
echo "=========================================================="
echo "  Starting Erowid SafeDB Desktop Application..."
echo "=========================================================="
python3 gui.py

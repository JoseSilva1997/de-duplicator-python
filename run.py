"""Top-level launcher for packaging with PyInstaller.

app.py uses package-relative imports, so it can't be handed to PyInstaller
directly. This script provides an absolute entry point instead.
"""
import sys

from guest_list_deduplicator.app import main

sys.exit(main())

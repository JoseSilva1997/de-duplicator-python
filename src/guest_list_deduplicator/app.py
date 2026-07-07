"""Entry point: configures the Qt app, applies a light theme, shows the main window."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import qdarktheme
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def _icon_path() -> Path:
    """Locate the app icon both in dev and when frozen by PyInstaller.

    PyInstaller unpacks bundled data files to sys._MEIPASS; in dev the icon
    lives under src/assets. Both layouts put it at <base>/assets/<file>.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[1]  # the src/ directory
    return base / "assets" / "cut_duplicates_icon_256.ico"


def _self_check() -> int:
    """Construct the app and main window offscreen, then exit without running
    the event loop.

    This is a packaging smoke test, not a functional one. Running the frozen
    exe with --self-check forces the whole import chain (including bundled
    dependencies such as numpy) and Qt widget construction, so a module the
    PyInstaller build failed to collect surfaces here as a non-zero exit in CI.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.close()
    return 0


def main() -> int:
    if "--self-check" in sys.argv:
        return _self_check()
    app = QApplication(sys.argv)
    app.setApplicationName("Guest List Cleaner")
    app.setWindowIcon(QIcon(str(_icon_path())))
    qdarktheme.setup_theme("light", custom_colors={"primary": "#2563EB"})
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

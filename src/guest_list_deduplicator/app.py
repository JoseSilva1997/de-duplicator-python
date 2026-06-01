"""Entry point: configures the Qt app, applies a light theme, shows the main window."""
from __future__ import annotations

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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Guest List Cleaner")
    app.setWindowIcon(QIcon(str(_icon_path())))
    qdarktheme.setup_theme("light", custom_colors={"primary": "#2563EB"})
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

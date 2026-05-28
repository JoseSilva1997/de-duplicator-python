"""Entry point: configures the Qt app, applies a light theme, shows the main window."""
from __future__ import annotations

import sys

import qdarktheme
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Guest List Cleaner")
    qdarktheme.setup_theme("light", custom_colors={"primary": "#2563EB"})
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

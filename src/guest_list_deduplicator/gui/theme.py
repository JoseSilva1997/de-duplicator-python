"""Single source of colours, fonts, and sizing for the GUI."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont

# Surfaces
BACKGROUND = QColor("#FFFFFF")
CARD = QColor("#FFFFFF")
CARD_BORDER = QColor("#E2E8F0")
CARD_BORDER_HOVER = QColor("#CBD5E1")

# Primary
PRIMARY = QColor("#2563EB")
PRIMARY_HOVER = QColor("#1D4ED8")
PRIMARY_DISABLED = QColor("#C7D7FA")

# Text
TEXT_PRIMARY = QColor("#0F172A")
TEXT_SECONDARY = QColor("#64748B")
TEXT_MUTED = QColor("#94A3B8")

# Semantic
DANGER = QColor("#DC2626")
SUCCESS = QColor("#159A45")
SUCCESS_BG = QColor("#E7F8EE")
NEUTRAL_BG = QColor("#F1F5F9")

FONT_FAMILY = "Segoe UI"
CARD_ARC = 14


def font(size: int = 13, *, bold: bool = False) -> QFont:
    f = QFont(FONT_FAMILY, size)
    f.setBold(bold)
    return f


# Convenience font presets used across the GUI widgets.
FONT_REGULAR = font(10)
FONT_MEDIUM = font(10)
FONT_BOLD = font(10, bold=True)
FONT_TITLE = font(13, bold=True)
FONT_DISPLAY = font(21, bold=True)


def hex_(color: QColor) -> str:
    return color.name()

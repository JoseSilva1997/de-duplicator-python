"""Modal dialog that lets the user pick which sheets from a workbook to use.

Returns the selected sheet names, or None if the user cancelled / picked none.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import theme


def pick_sheets(parent: QWidget | None, title: str, sheets: list[str]) -> list[str] | None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setStyleSheet(f"QDialog {{ background: {theme.hex_(theme.BACKGROUND)}; }}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(24, 22, 24, 20)
    root.setSpacing(0)

    heading = QLabel("Choose which sheets to include")
    heading.setFont(theme.font(11, bold=True))
    heading.setStyleSheet(f"color: {theme.hex_(theme.TEXT_PRIMARY)};")
    root.addWidget(heading)

    hint = QLabel("All sheets are selected by default.")
    hint.setFont(theme.FONT_REGULAR)
    hint.setStyleSheet(f"color: {theme.hex_(theme.TEXT_SECONDARY)};")
    hint.setContentsMargins(0, 2, 0, 12)
    root.addWidget(hint)

    check_panel = QWidget()
    check_panel.setStyleSheet(f"background: {theme.hex_(theme.CARD)};")
    check_layout = QVBoxLayout(check_panel)
    check_layout.setContentsMargins(12, 10, 12, 10)
    check_layout.setSpacing(2)
    boxes: list[QCheckBox] = []
    for sheet in sheets:
        cb = QCheckBox(sheet)
        cb.setChecked(True)
        cb.setFont(theme.FONT_REGULAR)
        cb.setStyleSheet(f"color: {theme.hex_(theme.TEXT_PRIMARY)};")
        check_layout.addWidget(cb)
        boxes.append(cb)
    check_layout.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidget(check_panel)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.StyledPanel)
    scroll.setMinimumSize(420, 280)
    root.addWidget(scroll)

    select_all = _ghost_button("Select all")
    select_none = _ghost_button("Select none")
    ok = _primary_button("OK")
    cancel = _ghost_button("Cancel")

    select_all.clicked.connect(lambda: [b.setChecked(True) for b in boxes])
    select_none.clicked.connect(lambda: [b.setChecked(False) for b in boxes])
    ok.clicked.connect(dialog.accept)
    cancel.clicked.connect(dialog.reject)
    ok.setDefault(True)

    button_row = QHBoxLayout()
    button_row.setContentsMargins(0, 16, 0, 0)
    button_row.setSpacing(6)
    button_row.addWidget(select_all)
    button_row.addWidget(select_none)
    button_row.addStretch(1)
    button_row.addSpacing(8)
    button_row.addWidget(cancel)
    button_row.addWidget(ok)
    root.addLayout(button_row)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    selected = [sheets[i] for i, b in enumerate(boxes) if b.isChecked()]
    return selected or None


def _primary_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFont(theme.FONT_BOLD)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"""
        QPushButton {{
            background: {theme.hex_(theme.PRIMARY)};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 22px;
        }}
        QPushButton:hover {{
            background: {theme.hex_(theme.PRIMARY_HOVER)};
        }}
        """
    )
    return b


def _ghost_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFont(theme.FONT_MEDIUM)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"""
        QPushButton {{
            background: {theme.hex_(theme.NEUTRAL_BG)};
            color: {theme.hex_(theme.TEXT_PRIMARY)};
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{
            background: {theme.hex_(theme.CARD_BORDER)};
        }}
        """
    )
    return b

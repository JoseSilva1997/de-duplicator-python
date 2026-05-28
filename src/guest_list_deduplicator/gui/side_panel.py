"""Slide-in side panel that hosts Settings and How it works tabs.

Lives as a child of the main window and is raise_()'d above the main content
instead of using a layered pane. A separate Scrim child darkens the rest of
the window while the panel is open and closes the panel when clicked.
"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import theme

PANEL_WIDTH = 340
ANIMATION_MS = 180
SCRIM_ALPHA = 0.40


class Scrim(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._alpha = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)

    def alpha(self) -> float:
        return self._alpha

    def set_alpha(self, value: float) -> None:
        self._alpha = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event) -> None:
        if self._alpha <= 0:
            return
        painter = QPainter(self)
        color = QColor(0, 0, 0, int(self._alpha * 255))
        painter.fillRect(self.rect(), color)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit()


class SidePanel(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._open = False
        self._scrim = Scrim(parent)
        self._scrim.clicked.connect(lambda: self.set_open(False))

        self.setStyleSheet(
            f"""
            QFrame#sidePanelRoot {{
                background: {theme.hex_(theme.CARD)};
                border-left: 1px solid {theme.hex_(theme.CARD_BORDER)};
            }}
            """
        )
        self.setObjectName("sidePanelRoot")
        self.setVisible(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(self._build_header())
        root.addWidget(self._build_tabs(), 1)

        self._panel_anim = QPropertyAnimation(self, b"pos", self)
        self._panel_anim.setDuration(ANIMATION_MS)
        self._panel_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_anim.finished.connect(self._on_animation_finished)

    # ---- header ---------------------------------------------------------------

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(18, 16, 12, 12)
        title = QLabel("Settings")
        title.setFont(theme.FONT_TITLE)
        title.setStyleSheet(f"color: {theme.hex_(theme.TEXT_PRIMARY)};")
        header.addWidget(title)
        header.addStretch(1)
        close = QPushButton()
        close.setIcon(qta.icon("mdi.close", color=theme.hex_(theme.TEXT_SECONDARY)))
        close.setFlat(True)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("Close")
        close.clicked.connect(lambda: self.set_open(False))
        header.addWidget(close)
        return header

    # ---- tabs -----------------------------------------------------------------

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setFont(theme.FONT_MEDIUM)
        tabs.addTab(self._build_settings_tab(), "Settings")
        tabs.addTab(self._build_how_it_works_tab(), "How it works")
        return tabs

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(6)

        section = QLabel("Extra filtering")
        section.setFont(theme.FONT_BOLD)
        section.setStyleSheet(f"color: {theme.hex_(theme.TEXT_PRIMARY)};")
        layout.addWidget(section)

        self._drop_no_email = QCheckBox("Remove guests with no email address")
        self._drop_no_email.setChecked(True)
        self._drop_no_email.setFont(theme.FONT_REGULAR)
        layout.addWidget(self._drop_no_email)

        layout.addStretch(1)
        return _wrap_scrollable(page)

    def _build_how_it_works_tab(self) -> QWidget:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setFrameShape(QFrame.Shape.NoFrame)
        browser.setHtml(_how_it_works_html())
        return browser

    # ---- public API -----------------------------------------------------------

    def is_drop_rows_without_email_enabled(self) -> bool:
        return self._drop_no_email.isChecked()

    def is_open(self) -> bool:
        return self._open

    def set_open(self, should_open: bool) -> None:
        if self._open == should_open and not self._panel_anim.state():
            return
        self._open = should_open
        if should_open:
            self.setVisible(True)
            self._scrim.setVisible(True)
            self._scrim.raise_()
            self.raise_()

        parent = self.parentWidget()
        if parent is None:
            return
        target_x = parent.width() - self.width() if should_open else parent.width()

        self._panel_anim.stop()
        self._panel_anim.setStartValue(self.pos())
        end_pos = self.pos()
        end_pos.setX(target_x)
        self._panel_anim.setEndValue(end_pos)
        self._panel_anim.start()

        self._animate_scrim(SCRIM_ALPHA if should_open else 0.0)

    def _animate_scrim(self, target: float) -> None:
        start = self._scrim.alpha()
        steps = 12
        from PySide6.QtCore import QTimer

        timer = QTimer(self)
        timer.setInterval(int(ANIMATION_MS / steps))
        step = [0]

        def tick() -> None:
            step[0] += 1
            t = step[0] / steps
            eased = 1 - (1 - t) ** 3
            self._scrim.set_alpha(start + (target - start) * eased)
            if step[0] >= steps:
                timer.stop()
                timer.deleteLater()

        timer.timeout.connect(tick)
        timer.start()

    def _on_animation_finished(self) -> None:
        if not self._open:
            self.setVisible(False)
            self._scrim.setVisible(False)

    def resync_bounds(self, parent_width: int, parent_height: int) -> None:
        x = parent_width - PANEL_WIDTH if self._open else parent_width
        self.setGeometry(x, 0, PANEL_WIDTH, parent_height)
        self._scrim.setGeometry(0, 0, parent_width, parent_height)


def _wrap_scrollable(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return scroll


def _how_it_works_html() -> str:
    body_style = f"font-family: '{theme.FONT_FAMILY}'; font-size: 11pt; color: #0F172A;"
    h = "color:#0F172A; font-size:12pt; margin:14px 0 4px 0;"
    p = "color:#334155; margin:4px 0 10px 0; line-height:1.45;"
    li = "color:#334155; margin:2px 0; line-height:1.4;"
    return f"""
    <html><body style="{body_style}">
      <h3 style="{h}">What it does</h3>
      <p style="{p}">Compares a guest list against a list of confirmed attendees and
      produces a cleaned guest list with the duplicates removed. Accepts
      <b>.xlsx</b>, <b>.xls</b>, and <b>.csv</b> files.</p>

      <h3 style="{h}">Matching pipeline</h3>
      <p style="{p}">Each guest is checked against the attendees using five
      strategies in order. A guest is removed as soon as one strategy finds a match.</p>
      <ol>
        <li style="{li}"><b>Exact email</b> (confidence 100): same email address.</li>
        <li style="{li}"><b>Email username</b> (90): the part before the @ matches.</li>
        <li style="{li}"><b>Name and company</b> (90): first name, last name, and company all match exactly.</li>
        <li style="{li}"><b>Fuzzy key</b> (85): first name, last name, and company match approximately.</li>
        <li style="{li}"><b>Fuzzy name</b> (80+): names are similar enough to match, even without a company.</li>
      </ol>

      <h3 style="{h}">Output</h3>
      <p style="{p}">Two Excel files are written to your desktop:</p>
      <ul>
        <li style="{li}"><b>Updated guests list</b>: the cleaned guest list.</li>
        <li style="{li}"><b>People removed</b>: every removed guest with the reason and confidence for each match. Skipped entirely if no one was removed.</li>
      </ul>
      <p style="{p}">If you selected multiple sheets from a workbook, each sheet
      is deduplicated independently against the full pool of attendees, and the
      output files preserve that structure: one sheet in the output per sheet
      in the input. Sheets with no removals are omitted from the
      <b>People removed</b> file.</p>
      <p style="{p}">CSV inputs are treated as a single sheet named after the file.</p>
    </body></html>
    """

"""Drop-zone / file-chooser card. Emits `changed` whenever its file or record
count changes so the main window can refresh its status line."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .. import service
from . import theme
from .worker import Worker

SheetSelector = Callable[[Path], list[str] | None]
ACCEPTED_SUFFIXES = (".xlsx", ".xls", ".csv")
ICON_SIZE = 40


class FileCard(QFrame):
    changed = Signal()

    def __init__(self, title: str, description: str, sheet_selector: SheetSelector):
        super().__init__()
        self._sheet_selector = sheet_selector

        self._selected_file: Path | None = None
        self._selected_sheets: list[str] = []
        self._record_count: int = -1
        self._full_filename: str = ""
        self._drag_hover = False
        self._mouse_hover = False
        self._count_worker: Worker | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(0)

        self._title_label = self._make_label(title, theme.FONT_TITLE, theme.TEXT_PRIMARY)
        self._desc_label = self._make_label(description, theme.FONT_REGULAR, theme.TEXT_SECONDARY)
        self._desc_label.setContentsMargins(0, 6, 0, 18)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setContentsMargins(0, 0, 0, 12)
        self._icon_label.setStyleSheet("background: transparent;")
        self._set_icon("empty")

        self._main_label = self._make_label(
            "Choose a file or drag it here", theme.FONT_MEDIUM, theme.TEXT_SECONDARY
        )
        self._detail_label = self._make_label(" ", theme.FONT_REGULAR, theme.TEXT_MUTED)
        self._detail_label.setContentsMargins(0, 6, 0, 0)

        layout.addWidget(self._title_label)
        layout.addWidget(self._desc_label)
        layout.addStretch(1)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._main_label)
        layout.addWidget(self._detail_label)
        layout.addStretch(1)

    @staticmethod
    def _make_label(text: str, font: QFont, color: QColor) -> QLabel:
        label = QLabel(text)
        label.setFont(font)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        # palette/stylesheet would be heavier; setStyleSheet is fine for color-only
        label.setStyleSheet(f"color: {theme.hex_(color)}; background: transparent;")
        return label

    def _set_icon(self, state: str) -> None:
        # state: "empty" | "hover" | "loaded"
        if state == "loaded":
            icon = qta.icon("mdi.check-circle-outline", color=theme.hex_(theme.SUCCESS))
        elif state == "hover":
            icon = qta.icon("fa5s.download", color=theme.hex_(theme.PRIMARY))
        else:
            icon = qta.icon("fa5s.download", color=theme.hex_(theme.TEXT_MUTED))
        self._icon_label.setPixmap(icon.pixmap(ICON_SIZE, ICON_SIZE))

    # ---- state queries used by the main window --------------------------------

    def has_file(self) -> bool:
        return self._selected_file is not None

    def file(self) -> Path | None:
        return self._selected_file

    def selected_sheets(self) -> list[str]:
        return list(self._selected_sheets)

    def record_count(self) -> int:
        return self._record_count

    # ---- mouse + hover --------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_file_chooser()
        super().mousePressEvent(event)

    def enterEvent(self, event: QEvent) -> None:
        self._set_mouse_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._set_mouse_hover(False)
        super().leaveEvent(event)

    def _set_mouse_hover(self, on: bool) -> None:
        if self._mouse_hover == on:
            return
        self._mouse_hover = on
        self.update()

    # ---- drag and drop --------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_hover(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QEvent) -> None:
        self._set_drag_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_hover(False)
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        path = Path(urls[0].toLocalFile())
        if _is_accepted_file(path):
            event.acceptProposedAction()
            self._accept_file(path)
        else:
            event.ignore()
            self._show_unsupported_file_error(path)

    def _set_drag_hover(self, on: bool) -> None:
        if self._drag_hover == on:
            return
        self._drag_hover = on
        if not self.has_file():
            self._set_icon("hover" if on else "empty")
            self._main_label.setStyleSheet(
                f"color: {theme.hex_(theme.PRIMARY if on else theme.TEXT_SECONDARY)}; background: transparent;"
            )
        self.update()

    # ---- paint ----------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        arc = theme.CARD_ARC
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        background = theme.NEUTRAL_BG if (self._mouse_hover or self._drag_hover) else theme.CARD
        painter.setBrush(background)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, arc, arc)

        if self._drag_hover:
            pen = QPen(theme.PRIMARY, 1.8)
        elif self.has_file():
            pen = QPen(theme.SUCCESS, 1.8 if self._mouse_hover else 1.4)
        else:
            border_color = theme.TEXT_SECONDARY if self._mouse_hover else theme.TEXT_MUTED
            pen = QPen(border_color, 1.4, Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([6, 5])
        pen.setCosmetic(False)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, arc, arc)
        painter.end()
        super().paintEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_filename_display()

    # ---- file handling --------------------------------------------------------

    def _open_file_chooser(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select spreadsheet",
            "",
            "Spreadsheets (*.xlsx *.xls *.csv)",
        )
        if path_str:
            self._accept_file(Path(path_str))

    def _accept_file(self, chosen: Path) -> None:
        sheets = self._sheet_selector(chosen)
        if sheets is None:
            return  # user cancelled picker — keep current state

        self._selected_file = chosen
        self._selected_sheets = sheets
        self._record_count = -1
        self._full_filename = chosen.name

        self._set_icon("loaded")
        self._main_label.setStyleSheet(f"color: {theme.hex_(theme.TEXT_PRIMARY)}; background: transparent;")
        self._main_label.setToolTip(self._full_filename)
        self._update_filename_display()
        self._detail_label.setText(_format_sheet_summary(len(sheets), -1))

        self.update()
        self.changed.emit()
        self._count_records_async(chosen, sheets)

    def _count_records_async(self, file: Path, sheets: list[str]) -> None:
        # Cancel any in-flight count from a previous selection.
        if self._count_worker is not None:
            self._count_worker.requestInterruption()

        worker = Worker(service.count_records, file, sheets)
        self._count_worker = worker

        def on_succeeded(count: object) -> None:
            if file != self._selected_file:
                return  # stale: user picked a different file in the meantime
            self._record_count = int(count) if isinstance(count, int) else -1
            self._detail_label.setText(_format_sheet_summary(len(sheets), self._record_count))
            self.changed.emit()

        def on_failed(_ex: Exception) -> None:
            if file != self._selected_file:
                return
            self._record_count = -1
            self.changed.emit()

        def on_finished() -> None:
            # Drop our reference before the C++ object is deleted, so a later
            # selection never calls into a dangling wrapper. Guard against a
            # newer worker having already taken the slot.
            if self._count_worker is worker:
                self._count_worker = None
            worker.deleteLater()

        worker.succeeded.connect(on_succeeded)
        worker.failed.connect(on_failed)
        worker.finished.connect(on_finished)
        worker.start()

    def _update_filename_display(self) -> None:
        if not self._full_filename:
            self._main_label.setText("Choose a file or drag it here")
            return
        fm = QFontMetrics(self._main_label.font())
        margins = self.contentsMargins()
        available = self.width() - margins.left() - margins.right() - 8
        if available <= 0:
            return
        elided = fm.elidedText(self._full_filename, Qt.TextElideMode.ElideRight, available)
        self._main_label.setText(elided)

    def _show_unsupported_file_error(self, file: Path) -> None:
        suffix = file.suffix
        if suffix:
            description = f"is a {suffix} file"
        else:
            description = "is not a supported file type"
        QMessageBox.critical(
            self,
            "Unsupported file",
            f'"{file.name}" {description}.\n'
            "Please drop an Excel or CSV file (.xlsx, .xls, or .csv).",
        )


def _is_accepted_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ACCEPTED_SUFFIXES


def _format_sheet_summary(sheet_count: int, row_count: int) -> str:
    sheet_part = "1 sheet" if sheet_count == 1 else f"{sheet_count} sheets"
    if row_count < 0:
        return f"{sheet_part} selected"
    row_part = "1 row" if row_count == 1 else f"{row_count} rows"
    return f"{sheet_part} · {row_part}"

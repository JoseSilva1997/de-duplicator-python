"""Top-level window: two FileCards, a process button, status line, and a
side panel for settings."""
from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import service
from ..settings import UserSettings
from . import theme
from .file_card import FileCard
from .sheet_picker_dialog import pick_sheets
from .side_panel import SidePanel
from .worker import Worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guest List Cleaner")
        self.resize(900, 640)
        self.setMinimumSize(720, 520)

        central = QWidget()
        central.setStyleSheet(f"background: {theme.hex_(theme.BACKGROUND)};")
        self.setCentralWidget(central)

        # Side panel + scrim are children of the central widget, raised above
        # the main layout. They live outside the main QVBoxLayout so they can
        # overlay it without affecting reflow.
        self._side_panel = SidePanel(central)
        self._side_panel.resync_bounds(self.width(), self.height())

        self._guest_card = FileCard(
            "Guest list",
            "Upload your complete guest list",
            self._select_sheets_for,
        )
        self._attendee_card = FileCard(
            "Attendee list",
            "Upload your confirmed attendees list",
            self._select_sheets_for,
        )
        self._guest_card.changed.connect(self._refresh_process_button)
        self._attendee_card.changed.connect(self._refresh_process_button)

        self._process_button = self._build_process_button()
        self._status_label = QLabel("Upload both files to begin")
        self._status_label.setFont(theme.font(10))
        self._status_label.setStyleSheet(f"color: {theme.hex_(theme.TEXT_SECONDARY)};")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setFixedSize(280, 6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)

        self._layout_components(central)
        self._refresh_process_button()
        self._run_worker: Worker | None = None

    # ---- layout ---------------------------------------------------------------

    def _layout_components(self, central: QWidget) -> None:
        root = QVBoxLayout(central)
        root.setContentsMargins(48, 36, 48, 32)
        root.setSpacing(0)

        root.addLayout(self._build_top_bar())
        root.addLayout(self._build_header())
        root.addSpacing(28)
        root.addLayout(self._build_cards_row())
        root.addSpacing(32)
        root.addWidget(self._process_button, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addSpacing(14)
        root.addWidget(self._progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addSpacing(10)
        root.addWidget(self._status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addStretch(1)

    def _build_top_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addStretch(1)
        gear = QPushButton()
        gear.setIcon(qta.icon("mdi.cog-outline", color=theme.hex_(theme.TEXT_SECONDARY)))
        gear.setFlat(True)
        gear.setCursor(Qt.CursorShape.PointingHandCursor)
        gear.setToolTip("Settings and how it works")
        gear.clicked.connect(lambda: self._side_panel.set_open(not self._side_panel.is_open()))
        bar.addWidget(gear)
        return bar

    def _build_header(self) -> QVBoxLayout:
        header = QVBoxLayout()
        title = QLabel("Guest List Cleaner")
        title.setFont(theme.FONT_DISPLAY)
        title.setStyleSheet(f"color: {theme.hex_(theme.TEXT_PRIMARY)};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Deduplicate your guest list against confirmed attendees")
        subtitle.setFont(theme.font(11))
        subtitle.setStyleSheet(f"color: {theme.hex_(theme.TEXT_SECONDARY)};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setContentsMargins(0, 6, 0, 14)

        accent = QWidget()
        accent.setFixedSize(56, 3)
        accent.setStyleSheet(f"background: {theme.hex_(theme.PRIMARY)};")
        accent_row = QHBoxLayout()
        accent_row.addStretch(1)
        accent_row.addWidget(accent)
        accent_row.addStretch(1)

        header.addWidget(title)
        header.addWidget(subtitle)
        header.addLayout(accent_row)
        return header

    def _build_cards_row(self) -> QGridLayout:
        row = QGridLayout()
        row.setHorizontalSpacing(22)
        row.addWidget(self._guest_card, 0, 0)
        row.addWidget(self._attendee_card, 0, 1)
        row.setColumnStretch(0, 1)
        row.setColumnStretch(1, 1)
        return row

    def _build_process_button(self) -> QPushButton:
        button = QPushButton("Remove duplicates")
        button.setFont(theme.font(11, bold=True))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(self._process_button_qss(enabled=False))
        button.clicked.connect(self._on_remove_duplicates)
        return button

    @staticmethod
    def _process_button_qss(*, enabled: bool) -> str:
        bg = theme.PRIMARY if enabled else theme.PRIMARY_DISABLED
        return f"""
        QPushButton {{
            background: {theme.hex_(bg)};
            color: white;
            border: none;
            border-radius: 16px;
            padding: 12px 36px;
        }}
        QPushButton:hover:enabled {{
            background: {theme.hex_(theme.PRIMARY_HOVER)};
        }}
        """

    # ---- side panel + scrim sizing -------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._side_panel is not None:
            self._side_panel.resync_bounds(
                self.centralWidget().width(), self.centralWidget().height()
            )

    # ---- sheet selection callback used by both FileCards ---------------------

    def _select_sheets_for(self, file: Path) -> list[str] | None:
        try:
            sheets = service.list_sheets(file)
        except Exception as ex:
            self._show_error("Could not read sheet list", ex)
            return None
        if not sheets:
            self._show_error(
                "No usable sheets", RuntimeError("File contains no visible sheets.")
            )
            return None
        if len(sheets) == 1:
            return sheets  # auto-select single-sheet files
        return pick_sheets(self, f"Select sheets in {file.name}", sheets)

    # ---- process button state ------------------------------------------------

    def _refresh_process_button(self) -> None:
        ready = self._guest_card.has_file() and self._attendee_card.has_file()
        self._process_button.setEnabled(ready)
        self._process_button.setStyleSheet(self._process_button_qss(enabled=ready))

        if not ready:
            self._status_label.setText("Upload both files to begin")
            self._status_label.setStyleSheet(f"color: {theme.hex_(theme.TEXT_SECONDARY)};")
            return

        guests = self._guest_card.record_count()
        attendees = self._attendee_card.record_count()
        if guests < 0 or attendees < 0:
            self._status_label.setText("Ready to process · counting rows…")
        else:
            guest_word = "guest" if guests == 1 else "guests"
            attendee_word = "attendee" if attendees == 1 else "attendees"
            self._status_label.setText(
                f"Ready to process · {guests} {guest_word} and {attendees} {attendee_word}"
            )
        self._status_label.setStyleSheet(f"color: {theme.hex_(theme.SUCCESS)};")

    # ---- run -----------------------------------------------------------------

    def _on_remove_duplicates(self) -> None:
        primary_path = self._guest_card.file()
        secondary_path = self._attendee_card.file()
        assert primary_path is not None and secondary_path is not None

        settings = UserSettings(
            drop_rows_without_email=self._side_panel.is_drop_rows_without_email_enabled()
        )

        self._process_button.setEnabled(False)
        self._process_button.setStyleSheet(self._process_button_qss(enabled=False))
        self._status_label.setText("Processing…")
        self._status_label.setStyleSheet(f"color: {theme.hex_(theme.TEXT_SECONDARY)};")
        self._progress_bar.setVisible(True)

        worker = Worker(
            service.run,
            primary_path,
            self._guest_card.selected_sheets(),
            secondary_path,
            self._attendee_card.selected_sheets(),
            settings,
        )
        self._run_worker = worker
        worker.succeeded.connect(self._on_run_succeeded)
        worker.failed.connect(self._on_run_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_run_succeeded(self, summary: object) -> None:
        self._progress_bar.setVisible(False)
        self._refresh_process_button()
        self._show_summary(summary)

    def _on_run_failed(self, ex: Exception) -> None:
        self._progress_bar.setVisible(False)
        self._refresh_process_button()
        self._show_error("Processing failed", ex)

    # ---- dialogs -------------------------------------------------------------

    def _show_summary(self, summary) -> None:  # service.Summary
        lines = [
            f"Processed {summary.sheets_processed} sheet(s)",
            f"Kept:    {summary.total_kept}",
            f"Removed: {summary.total_removed}",
        ]
        if summary.no_email_dropped > 0:
            lines.append("")
            lines.append(f"Removed {summary.no_email_dropped} row(s) with no email")
        lines.append("")
        lines.append("Output saved to:")
        lines.append(str(summary.output_directory))
        QMessageBox.information(self, "Done", "\n".join(lines))

    def _show_error(self, title: str, ex: BaseException) -> None:
        QMessageBox.critical(self, "Error", f"{title}:\n{ex}")

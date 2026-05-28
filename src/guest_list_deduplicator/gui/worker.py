"""Small QThread wrapper that runs a callable off the GUI thread and emits
the result (or exception) back on the main thread via signals."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    succeeded = Signal(object)
    failed = Signal(Exception)

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as ex:
            self.failed.emit(ex)
        else:
            self.succeeded.emit(result)

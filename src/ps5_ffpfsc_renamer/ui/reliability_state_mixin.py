from __future__ import annotations

from dataclasses import replace

from ..ffpfsc_reader import set_mkpfs_executable
from ..operation_history import OperationHistory
from ..settings import AppSettings, load_settings


class ReliabilityStateMixin:
    """Reliability/session state shared by the desktop feature layers."""

    def __init__(self) -> None:
        initial_settings = load_settings()
        self._mkpfs_path: str | None = initial_settings.mkpfs_path
        sortable = getattr(self, "SORTABLE_COLUMNS", {})
        self._sort_column = (
            initial_settings.sort_column
            if initial_settings.sort_column in sortable
            else "file"
        )
        self._sort_descending = bool(initial_settings.sort_descending)
        self._last_unavailable_roots: tuple[str, ...] = ()
        self._last_failure_cache_hits = 0
        set_mkpfs_executable(self._mkpfs_path)
        self.history = OperationHistory()

        super().__init__()
        self._build_product_menu()
        self._install_shortcuts()
        self._refresh_sort_headings()

    def _apply_settings(self, settings: AppSettings) -> None:
        self._mkpfs_path = settings.mkpfs_path
        sortable = getattr(self, "SORTABLE_COLUMNS", {})
        self._sort_column = settings.sort_column if settings.sort_column in sortable else "file"
        self._sort_descending = bool(settings.sort_descending)
        set_mkpfs_executable(self._mkpfs_path)
        super()._apply_settings(settings)

    def _snapshot_settings(self) -> AppSettings:
        return replace(
            super()._snapshot_settings(),
            mkpfs_path=self._mkpfs_path,
            sort_column=self._sort_column,
            sort_descending=self._sort_descending,
        )

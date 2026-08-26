from __future__ import annotations

from pathlib import Path

from ..diagnostics import classify_reader_error, infer_metadata_from_path
from ..metadata import GameMetadata

PartialItem = tuple[Path, GameMetadata, str, str, str, str]


class PartialMetadataMixin:
    """Display-only path fallback for MkPFS failures, aware of multi-root libraries."""

    def __init__(self) -> None:
        self.partial_items: list[PartialItem] = []
        super().__init__()

    def _scan(self) -> None:
        self.partial_items = []
        super()._scan()

    def _scan_complete(
        self,
        parsed: list[tuple[Path, GameMetadata]],
        errors: list[tuple[Path, str]],
        total: int,
        started_at: float,
        workers: int,
        cache_hits: int,
        mkpfs_reads: int,
    ) -> None:
        partial: list[PartialItem] = []
        hard_errors: list[tuple[Path, str]] = []

        for image, detail in errors:
            inferred = infer_metadata_from_path(
                image,
                library_root=self._matching_root(image),
            )
            code, friendly = classify_reader_error(detail)
            if inferred is None:
                hard_errors.append((image, detail))
                continue
            partial.append(
                (
                    image,
                    inferred.metadata,
                    detail,
                    inferred.source,
                    code,
                    friendly,
                )
            )

        self.partial_items = partial
        super()._scan_complete(
            parsed,
            hard_errors,
            total,
            started_at,
            workers,
            cache_hits,
            mkpfs_reads,
        )

        partial_count = len(partial)
        hard_count = len(hard_errors)
        root_count = len(self.library_roots)
        if partial_count:
            self.progress_note_var.set(
                f"Scan complete across {root_count} folder(s): {cache_hits} reused from cache, "
                f"{mkpfs_reads} read with MkPFS, {partial_count} shown as PARTIAL. "
                "Path-derived metadata is display-only and is never used for automatic rename."
            )
        else:
            self.progress_note_var.set(
                f"Scan complete across {root_count} folder(s): {cache_hits} reused from cache, "
                f"{mkpfs_reads} read with MkPFS."
            )
        self.status_var.set(
            f"Scan complete — {root_count} folder(s), {cache_hits} cached, "
            f"{mkpfs_reads} new/changed, {partial_count} partial, {hard_count} error(s)"
        )

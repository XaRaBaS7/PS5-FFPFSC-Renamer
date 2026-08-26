from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanProfile:
    total_files: int
    selected_roots: int
    effective_roots: int
    unavailable_roots: int
    cache_hits: int
    failure_cache_hits: int
    mkpfs_reads: int
    workers: int
    root_probe_seconds: float
    discovery_seconds: float
    cache_seconds: float
    mkpfs_seconds: float
    total_seconds: float

    @property
    def cache_hit_ratio(self) -> float:
        return (self.cache_hits / self.total_files) if self.total_files else 0.0

    @property
    def files_per_second(self) -> float:
        return (self.total_files / self.total_seconds) if self.total_seconds > 0 else 0.0

    def compact_summary(self) -> str:
        return (
            f"roots {self.root_probe_seconds:.2f}s • discovery {self.discovery_seconds:.2f}s • "
            f"cache {self.cache_seconds:.2f}s • MkPFS {self.mkpfs_seconds:.2f}s • "
            f"total {self.total_seconds:.2f}s"
        )

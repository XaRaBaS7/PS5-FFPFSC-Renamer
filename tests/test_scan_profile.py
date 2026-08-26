from ps5_ffpfsc_renamer.scan_profile import ScanProfile


def test_scan_profile_derived_metrics() -> None:
    profile = ScanProfile(
        total_files=100,
        selected_roots=3,
        effective_roots=2,
        unavailable_roots=1,
        cache_hits=80,
        failure_cache_hits=4,
        mkpfs_reads=20,
        workers=4,
        root_probe_seconds=0.1,
        discovery_seconds=0.2,
        cache_seconds=0.3,
        mkpfs_seconds=1.4,
        total_seconds=2.0,
    )

    assert profile.cache_hit_ratio == 0.8
    assert profile.files_per_second == 50.0
    summary = profile.compact_summary()
    assert "discovery 0.20s" in summary
    assert "MkPFS 1.40s" in summary
    assert "total 2.00s" in summary


def test_empty_scan_profile_has_safe_ratios() -> None:
    profile = ScanProfile(
        total_files=0,
        selected_roots=0,
        effective_roots=0,
        unavailable_roots=0,
        cache_hits=0,
        failure_cache_hits=0,
        mkpfs_reads=0,
        workers=1,
        root_probe_seconds=0.0,
        discovery_seconds=0.0,
        cache_seconds=0.0,
        mkpfs_seconds=0.0,
        total_seconds=0.0,
    )

    assert profile.cache_hit_ratio == 0.0
    assert profile.files_per_second == 0.0

from __future__ import annotations

from .desktop_core import RenamerApp as DesktopCore
from .process_utils import terminate_registered_processes
from .ui.activity_progress_mixin import ActivityProgressMixin
from .ui.details_cache_maintenance_mixin import DetailsCacheMaintenanceMixin
from .ui.details_prefetch_mixin import DetailsPrefetchMixin
from .ui.duplicate_manager_mixin import DuplicateManagerMixin
from .ui.feedback_mixin import FeedbackMixin
from .ui.filename_builder_mixin import FilenameBuilderMixin
from .ui.game_details_mixin import GameDetailsMixin
from .ui.keyboard_shortcuts_mixin import KeyboardShortcutsMixin
from .ui.library_context_menu_mixin import LibraryContextMenuMixin
from .ui.library_export_mixin import LibraryExportMixin
from .ui.library_health_mixin import LibraryHealthMixin
from .ui.library_insights_mixin import LibraryInsightsMixin
from .ui.library_tools_mixin import LibraryToolsMixin
from .ui.library_workspace_mixin import LibraryWorkspaceMixin
from .ui.live_watch_mixin import LiveWatchMixin
from .ui.live_watch_reporting_mixin import LiveWatchReportingMixin
from .ui.metadata_cache_manager_mixin import MetadataCacheManagerMixin
from .ui.mkpfs_engine_dialog_mixin import MkPFSEngineDialogMixin
from .ui.multi_root_library_mixin import MultiRootLibraryMixin
from .ui.multi_selection_details_mixin import MultiSelectionDetailsMixin
from .ui.naming_profiles_mixin import NamingProfilesMixin
from .ui.offline_root_records_mixin import OfflineRootRecordsMixin
from .ui.operation_history_mixin import OperationHistoryMixin
from .ui.optimized_scan_mixin import OptimizedScanMixin
from .ui.options_dialog_mixin import OptionsDialogMixin
from .ui.partial_metadata_mixin import PartialMetadataMixin
from .ui.preserved_view_guard_mixin import PreservedViewGuardMixin
from .ui.product_menu_mixin import ProductMenuMixin
from .ui.reanalysis_mixin import ReanalysisMixin
from .ui.recycle_bin_mixin import RecycleBinMixin
from .ui.reliability_state_mixin import ReliabilityStateMixin
from .ui.rename_journal_mixin import RenameJournalMixin
from .ui.rename_manifest_mixin import RenameManifestMixin
from .ui.rename_safety_mixin import RenameSafetyMixin
from .ui.result_actions_mixin import ResultActionsMixin
from .ui.runtime_experience_mixin import RuntimeExperienceMixin
from .ui.scan_diff_mixin import ScanDiffMixin
from .ui.scan_view_restore_mixin import ScanViewRestoreMixin
from .ui.self_test_mixin import SelfTestMixin
from .ui.settings_backup_mixin import SettingsBackupMixin
from .ui.shell_misc_mixin import ShellMiscMixin
from .ui.sortable_results_mixin import SortableResultsMixin
from .ui.startup_preferences_mixin import StartupPreferencesMixin
from .ui.status_summary_mixin import StatusSummaryMixin
from .ui.undo_cache_mixin import UndoCacheMixin
from .ui.workspace_layout_mixin import WorkspaceLayoutMixin
from .ui.workspace_preferences_mixin import WorkspacePreferencesMixin


class RenamerApp(
    RenameSafetyMixin,
    WorkspaceLayoutMixin,
    SelfTestMixin,
    UndoCacheMixin,
    PreservedViewGuardMixin,
    LiveWatchReportingMixin,
    MultiSelectionDetailsMixin,
    DetailsPrefetchMixin,
    LibraryInsightsMixin,
    NamingProfilesMixin,
    DetailsCacheMaintenanceMixin,
    LiveWatchMixin,
    GameDetailsMixin,
    ScanViewRestoreMixin,
    RuntimeExperienceMixin,
    ActivityProgressMixin,
    ScanDiffMixin,
    OfflineRootRecordsMixin,
    RenameManifestMixin,
    MkPFSEngineDialogMixin,
    StartupPreferencesMixin,
    SettingsBackupMixin,
    FeedbackMixin,
    DuplicateManagerMixin,
    ProductMenuMixin,
    OptionsDialogMixin,
    StatusSummaryMixin,
    SortableResultsMixin,
    KeyboardShortcutsMixin,
    OptimizedScanMixin,
    ReanalysisMixin,
    LibraryExportMixin,
    OperationHistoryMixin,
    LibraryHealthMixin,
    MetadataCacheManagerMixin,
    ShellMiscMixin,
    RenameJournalMixin,
    ReliabilityStateMixin,
    LibraryContextMenuMixin,
    LibraryToolsMixin,
    RecycleBinMixin,
    LibraryWorkspaceMixin,
    WorkspacePreferencesMixin,
    MultiRootLibraryMixin,
    PartialMetadataMixin,
    ResultActionsMixin,
    FilenameBuilderMixin,
    DesktopCore,
):
    """Canonical desktop application entry point."""


def main() -> None:
    app = RenamerApp()
    try:
        app.mainloop()
    finally:
        # No MkPFS helper may outlive the desktop process. This also covers
        # cancellation/close races while a bounded metadata read is active.
        terminate_registered_processes()


if __name__ == "__main__":
    main()

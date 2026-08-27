from __future__ import annotations

from ps5_ffpfsc_renamer import desktop
from ps5_ffpfsc_renamer.desktop_core import RenamerApp as DesktopCore
from ps5_ffpfsc_renamer.gui_v10 import RenamerApp as LegacyRenamerAppV10
from ps5_ffpfsc_renamer.gui_v9 import RenamerApp as LegacyRenamerAppV9
from ps5_ffpfsc_renamer.gui_v8 import RenamerApp as LegacyRenamerAppV8
from ps5_ffpfsc_renamer.gui_v7 import RenamerApp as LegacyRenamerAppV7
from ps5_ffpfsc_renamer.gui_v6 import RenamerApp as LegacyRenamerAppV6
from ps5_ffpfsc_renamer.gui_v5 import RenamerApp as LegacyRenamerAppV5
from ps5_ffpfsc_renamer.gui_v4 import RenamerApp as LegacyRenamerAppV4
from ps5_ffpfsc_renamer.gui_v3 import RenamerApp as LegacyRenamerAppV3
from ps5_ffpfsc_renamer.gui_v2 import RenamerApp as LegacyRenamerAppV2
from ps5_ffpfsc_renamer.ui.activity_progress_mixin import ActivityProgressMixin
from ps5_ffpfsc_renamer.ui.details_cache_maintenance_mixin import DetailsCacheMaintenanceMixin
from ps5_ffpfsc_renamer.ui.details_prefetch_mixin import DetailsPrefetchMixin
from ps5_ffpfsc_renamer.ui.duplicate_manager_mixin import DuplicateManagerMixin
from ps5_ffpfsc_renamer.ui.feedback_mixin import FeedbackMixin
from ps5_ffpfsc_renamer.ui.filename_builder_mixin import FilenameBuilderMixin
from ps5_ffpfsc_renamer.ui.game_details_mixin import GameDetailsMixin
from ps5_ffpfsc_renamer.ui.keyboard_shortcuts_mixin import KeyboardShortcutsMixin
from ps5_ffpfsc_renamer.ui.library_context_menu_mixin import LibraryContextMenuMixin
from ps5_ffpfsc_renamer.ui.library_export_mixin import LibraryExportMixin
from ps5_ffpfsc_renamer.ui.library_health_mixin import LibraryHealthMixin
from ps5_ffpfsc_renamer.ui.library_insights_mixin import LibraryInsightsMixin
from ps5_ffpfsc_renamer.ui.library_tools_mixin import LibraryToolsMixin
from ps5_ffpfsc_renamer.ui.library_workspace_mixin import LibraryWorkspaceMixin
from ps5_ffpfsc_renamer.ui.live_watch_mixin import LiveWatchMixin
from ps5_ffpfsc_renamer.ui.live_watch_reporting_mixin import LiveWatchReportingMixin
from ps5_ffpfsc_renamer.ui.metadata_cache_manager_mixin import MetadataCacheManagerMixin
from ps5_ffpfsc_renamer.ui.mkpfs_engine_dialog_mixin import MkPFSEngineDialogMixin
from ps5_ffpfsc_renamer.ui.multi_root_library_mixin import MultiRootLibraryMixin
from ps5_ffpfsc_renamer.ui.multi_selection_details_mixin import MultiSelectionDetailsMixin
from ps5_ffpfsc_renamer.ui.naming_profiles_mixin import NamingProfilesMixin
from ps5_ffpfsc_renamer.ui.offline_root_records_mixin import OfflineRootRecordsMixin
from ps5_ffpfsc_renamer.ui.operation_history_mixin import OperationHistoryMixin
from ps5_ffpfsc_renamer.ui.optimized_scan_mixin import OptimizedScanMixin
from ps5_ffpfsc_renamer.ui.options_dialog_mixin import OptionsDialogMixin
from ps5_ffpfsc_renamer.ui.partial_metadata_mixin import PartialMetadataMixin
from ps5_ffpfsc_renamer.ui.preserved_view_guard_mixin import PreservedViewGuardMixin
from ps5_ffpfsc_renamer.ui.product_menu_mixin import ProductMenuMixin
from ps5_ffpfsc_renamer.ui.reanalysis_mixin import ReanalysisMixin
from ps5_ffpfsc_renamer.ui.recycle_bin_mixin import RecycleBinMixin
from ps5_ffpfsc_renamer.ui.reliability_state_mixin import ReliabilityStateMixin
from ps5_ffpfsc_renamer.ui.rename_journal_mixin import RenameJournalMixin
from ps5_ffpfsc_renamer.ui.rename_manifest_mixin import RenameManifestMixin
from ps5_ffpfsc_renamer.ui.rename_safety_mixin import RenameSafetyMixin
from ps5_ffpfsc_renamer.ui.result_actions_mixin import ResultActionsMixin
from ps5_ffpfsc_renamer.ui.runtime_experience_mixin import RuntimeExperienceMixin
from ps5_ffpfsc_renamer.ui.scan_diff_mixin import ScanDiffMixin
from ps5_ffpfsc_renamer.ui.scan_view_restore_mixin import ScanViewRestoreMixin
from ps5_ffpfsc_renamer.ui.self_test_mixin import SelfTestMixin
from ps5_ffpfsc_renamer.ui.settings_backup_mixin import SettingsBackupMixin
from ps5_ffpfsc_renamer.ui.shell_misc_mixin import ShellMiscMixin
from ps5_ffpfsc_renamer.ui.sortable_results_mixin import SortableResultsMixin
from ps5_ffpfsc_renamer.ui.startup_preferences_mixin import StartupPreferencesMixin
from ps5_ffpfsc_renamer.ui.status_summary_mixin import StatusSummaryMixin
from ps5_ffpfsc_renamer.ui.undo_cache_mixin import UndoCacheMixin
from ps5_ffpfsc_renamer.ui.workspace_preferences_mixin import WorkspacePreferencesMixin


def test_desktop_is_fully_non_versioned_at_runtime() -> None:
    assert desktop.RenamerApp.__module__ == "ps5_ffpfsc_renamer.desktop"
    expected = (
        RenameSafetyMixin,
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
    )
    assert desktop.RenamerApp.__mro__[1 : 1 + len(expected)] == expected
    for legacy in (
        LegacyRenamerAppV10,
        LegacyRenamerAppV9,
        LegacyRenamerAppV8,
        LegacyRenamerAppV7,
        LegacyRenamerAppV6,
        LegacyRenamerAppV5,
        LegacyRenamerAppV4,
        LegacyRenamerAppV3,
        LegacyRenamerAppV2,
    ):
        assert legacy not in desktop.RenamerApp.__mro__


def test_desktop_preserves_critical_hook_order() -> None:
    mro = desktop.RenamerApp.__mro__
    assert mro.index(PreservedViewGuardMixin) < mro.index(DetailsPrefetchMixin)
    assert mro.index(PreservedViewGuardMixin) < mro.index(GameDetailsMixin)
    assert mro.index(PreservedViewGuardMixin) < mro.index(ReanalysisMixin)
    assert mro.index(PreservedViewGuardMixin) < mro.index(LibraryContextMenuMixin)
    assert mro.index(ScanViewRestoreMixin) < mro.index(RuntimeExperienceMixin) < mro.index(ActivityProgressMixin)
    assert mro.index(ActivityProgressMixin) < mro.index(ScanDiffMixin)
    assert mro.index(ScanDiffMixin) < mro.index(OfflineRootRecordsMixin) < mro.index(RenameManifestMixin)
    assert mro.index(ActivityProgressMixin) < mro.index(ScanDiffMixin) < mro.index(OptimizedScanMixin)
    assert mro.index(ScanDiffMixin) < mro.index(RenameManifestMixin) < mro.index(ProductMenuMixin)
    assert mro.index(SettingsBackupMixin) < mro.index(FeedbackMixin) < mro.index(DuplicateManagerMixin)
    assert mro.index(FeedbackMixin) < mro.index(ProductMenuMixin)
    assert mro.index(DuplicateManagerMixin) < mro.index(KeyboardShortcutsMixin)
    assert mro.index(StatusSummaryMixin) < mro.index(SortableResultsMixin)
    assert mro.index(DetailsPrefetchMixin) < mro.index(LibraryContextMenuMixin)
    assert mro.index(ActivityProgressMixin) < mro.index(OptimizedScanMixin) < mro.index(PartialMetadataMixin)
    assert mro.index(LibraryInsightsMixin) < mro.index(ScanDiffMixin) < mro.index(RenameJournalMixin)
    assert mro.index(StartupPreferencesMixin) < mro.index(ReliabilityStateMixin) < mro.index(WorkspacePreferencesMixin)
    assert mro.index(WorkspacePreferencesMixin) < mro.index(MultiRootLibraryMixin)


def test_desktop_critical_methods_are_extracted() -> None:
    assert desktop.RenamerApp._rename is RenameSafetyMixin._rename
    assert desktop.RenamerApp._execute_plan_transaction is RenameSafetyMixin._execute_plan_transaction
    assert desktop.RenamerApp._undo_transaction is UndoCacheMixin._undo_transaction
    assert desktop.RenamerApp._scan is ScanViewRestoreMixin._scan
    assert desktop.RenamerApp._scan_complete is ScanViewRestoreMixin._scan_complete
    assert desktop.RenamerApp._scan_worker is OptimizedScanMixin._scan_worker
    assert desktop.RenamerApp._build_table is SortableResultsMixin._build_table
    assert desktop.RenamerApp._record_model is LibraryWorkspaceMixin._record_model
    assert desktop.RenamerApp._show_context_menu is PreservedViewGuardMixin._show_context_menu
    assert desktop.RenamerApp._double_click is PreservedViewGuardMixin._double_click
    assert desktop.RenamerApp._prefetch_selected_details is PreservedViewGuardMixin._prefetch_selected_details
    assert desktop.RenamerApp._run_diagnostics is PreservedViewGuardMixin._run_diagnostics
    assert desktop.RenamerApp._analyze_paths is PreservedViewGuardMixin._analyze_paths
    assert desktop.RenamerApp._compare_duplicates is PreservedViewGuardMixin._compare_duplicates
    assert desktop.RenamerApp._activate_details_record is PreservedViewGuardMixin._activate_details_record
    assert desktop.RenamerApp._delete_records is RecycleBinMixin._delete_records
    assert desktop.RenamerApp._manage_folders is MultiRootLibraryMixin._manage_folders
    assert desktop.RenamerApp._friendly_reason is ResultActionsMixin._friendly_reason
    assert desktop.RenamerApp._render_order_editor is FilenameBuilderMixin._render_order_editor
    assert desktop.RenamerApp._show_naming_profiles is NamingProfilesMixin._show_naming_profiles
    assert desktop.RenamerApp._show_mkpfs_settings is MkPFSEngineDialogMixin._show_mkpfs_settings
    assert desktop.RenamerApp._export_library is LibraryExportMixin._export_library
    assert desktop.RenamerApp._export_selected is LibraryExportMixin._export_selected
    assert desktop.RenamerApp._export_rename_manifest is RenameManifestMixin._export_rename_manifest
    assert desktop.RenamerApp._export_settings_backup is SettingsBackupMixin._export_settings_backup
    assert desktop.RenamerApp._import_settings_backup is SettingsBackupMixin._import_settings_backup
    assert desktop.RenamerApp._show_feedback_dialog is FeedbackMixin._show_feedback_dialog
    assert desktop.RenamerApp.report_callback_exception is FeedbackMixin.report_callback_exception
    assert desktop.RenamerApp._build_product_menu is SelfTestMixin._build_product_menu
    assert desktop.RenamerApp._show_duplicate_manager is DuplicateManagerMixin._show_duplicate_manager
    assert desktop.RenamerApp._select_duplicate_rows is DuplicateManagerMixin._select_duplicate_rows
    assert desktop.RenamerApp._select_problem_rows is DuplicateManagerMixin._select_problem_rows
    assert desktop.RenamerApp._show_history_window is OperationHistoryMixin._show_history_window
    assert desktop.RenamerApp._show_library_health is LibraryHealthMixin._show_library_health
    assert desktop.RenamerApp._show_scan_changes is ScanDiffMixin._show_scan_changes
    assert desktop.RenamerApp._show_report is LibraryToolsMixin._show_report
    assert desktop.RenamerApp._show_about is ShellMiscMixin._show_about


def test_desktop_dynamic_feature_layers_remain_in_charge() -> None:
    assert desktop.RenamerApp._watch_result is LiveWatchReportingMixin._watch_result
    assert desktop.RenamerApp._watch_tick is LiveWatchMixin._watch_tick
    assert desktop.RenamerApp._on_details_selection is MultiSelectionDetailsMixin._on_details_selection
    assert desktop.RenamerApp._build_details_panel is GameDetailsMixin._build_details_panel
    assert desktop.RenamerApp._finalize_completed_rename is LibraryInsightsMixin._finalize_completed_rename
    assert desktop.RenamerApp._current_naming_options is NamingProfilesMixin._current_naming_options
    assert desktop.RenamerApp._snapshot_settings is NamingProfilesMixin._snapshot_settings
    assert desktop.RenamerApp._queue_save_preferences is WorkspacePreferencesMixin._queue_save_preferences
    assert desktop.RenamerApp._sort_by_column is SortableResultsMixin._sort_by_column
    assert desktop.RenamerApp._install_shortcuts is DuplicateManagerMixin._install_shortcuts

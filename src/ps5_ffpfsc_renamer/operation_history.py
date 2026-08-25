from __future__ import annotations

import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .renamer import RenameStep, _redo_steps, undo_forward_steps


@dataclass(frozen=True, slots=True)
class HistoryTransaction:
    transaction_id: str
    created_at: int
    label: str
    item_count: int
    undone_at: int | None
    pairs: tuple[tuple[Path, Path], ...]
    steps: tuple[RenameStep, ...]

    @property
    def is_undone(self) -> bool:
        return self.undone_at is not None


@dataclass(frozen=True, slots=True)
class UndoResult:
    transaction: HistoryTransaction
    restored_pairs: tuple[tuple[Path, Path], ...]
    retained_directories: tuple[Path, ...] = ()


class HistoryError(RuntimeError):
    pass


def default_history_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / "PS5-FFPFSC-Renamer"
    else:
        root = Path.home() / ".ps5-ffpfsc-renamer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "operation-history.sqlite3"


class OperationHistory:
    """Persistent operation journal for rename transactions.

    The database stores both final old/new file pairs and the lower-level
    filesystem steps required to restore Smart-folder and newly-created-folder
    layouts safely. No file contents are copied into the journal.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = (db_path or default_history_path()).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    undone_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS transaction_pairs (
                    transaction_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    old_path TEXT NOT NULL,
                    new_path TEXT NOT NULL,
                    PRIMARY KEY (transaction_id, seq),
                    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
                );

                CREATE TABLE IF NOT EXISTS transaction_steps (
                    transaction_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT,
                    destination TEXT NOT NULL,
                    PRIMARY KEY (transaction_id, seq),
                    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
                );

                CREATE INDEX IF NOT EXISTS idx_transactions_created_at
                ON transactions(created_at DESC);
                """
            )

    def record(
        self,
        *,
        label: str,
        pairs: Iterable[tuple[Path, Path]],
        steps: Iterable[RenameStep],
    ) -> str | None:
        pair_list = [(Path(old), Path(new)) for old, new in pairs if Path(old) != Path(new)]
        step_list = list(steps)
        if not pair_list or not step_list:
            return None

        transaction_id = uuid.uuid4().hex
        created_at = int(time.time())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO transactions(transaction_id, created_at, label, item_count, undone_at) "
                "VALUES (?, ?, ?, ?, NULL)",
                (transaction_id, created_at, label.strip() or "Rename", len(pair_list)),
            )
            connection.executemany(
                "INSERT INTO transaction_pairs(transaction_id, seq, old_path, new_path) "
                "VALUES (?, ?, ?, ?)",
                [
                    (transaction_id, index, str(old), str(new))
                    for index, (old, new) in enumerate(pair_list)
                ],
            )
            connection.executemany(
                "INSERT INTO transaction_steps(transaction_id, seq, kind, source, destination) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        transaction_id,
                        index,
                        step.kind,
                        str(step.source) if step.source is not None else None,
                        str(step.destination),
                    )
                    for index, step in enumerate(step_list)
                ],
            )
        return transaction_id

    def _load_transaction(self, transaction_id: str) -> HistoryTransaction | None:
        with self._connect() as connection:
            transaction = connection.execute(
                "SELECT * FROM transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
            if transaction is None:
                return None
            pair_rows = connection.execute(
                "SELECT * FROM transaction_pairs WHERE transaction_id = ? ORDER BY seq",
                (transaction_id,),
            ).fetchall()
            step_rows = connection.execute(
                "SELECT * FROM transaction_steps WHERE transaction_id = ? ORDER BY seq",
                (transaction_id,),
            ).fetchall()

        return HistoryTransaction(
            transaction_id=transaction["transaction_id"],
            created_at=int(transaction["created_at"]),
            label=transaction["label"],
            item_count=int(transaction["item_count"]),
            undone_at=int(transaction["undone_at"]) if transaction["undone_at"] is not None else None,
            pairs=tuple((Path(row["old_path"]), Path(row["new_path"])) for row in pair_rows),
            steps=tuple(
                RenameStep(
                    row["kind"],
                    Path(row["source"]) if row["source"] is not None else None,
                    Path(row["destination"]),
                )
                for row in step_rows
            ),
        )

    def get(self, transaction_id: str) -> HistoryTransaction | None:
        return self._load_transaction(transaction_id)

    def recent(self, limit: int = 50) -> list[HistoryTransaction]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            ids = [
                row["transaction_id"]
                for row in connection.execute(
                    "SELECT transaction_id FROM transactions "
                    "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            ]
        result: list[HistoryTransaction] = []
        for transaction_id in ids:
            transaction = self._load_transaction(transaction_id)
            if transaction is not None:
                result.append(transaction)
        return result

    def last_undoable(self) -> HistoryTransaction | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT transaction_id FROM transactions WHERE undone_at IS NULL "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return self._load_transaction(row["transaction_id"])

    @staticmethod
    def _validate_undo(transaction: HistoryTransaction) -> None:
        if transaction.is_undone:
            raise HistoryError("This transaction has already been undone.")

        for step in reversed(transaction.steps):
            if step.kind in {"rename_file", "rename_dir"}:
                if step.source is None:
                    raise HistoryError(f"History entry is missing the source for {step.kind}.")
                if not step.destination.exists():
                    raise HistoryError(
                        f"Undo cannot continue because the current path is missing:\n{step.destination}"
                    )
                if step.source.exists():
                    raise HistoryError(
                        f"Undo cannot overwrite an existing original path:\n{step.source}"
                    )
            elif step.kind == "mkdir":
                if step.destination.exists() and not step.destination.is_dir():
                    raise HistoryError(
                        f"Undo expected a directory but found another object:\n{step.destination}"
                    )
            else:
                raise HistoryError(f"Unsupported history step: {step.kind}")

    def undo_last(self) -> UndoResult:
        transaction = self.last_undoable()
        if transaction is None:
            raise HistoryError("There are no rename transactions to undo.")
        return self.undo(transaction.transaction_id)

    def undo(self, transaction_id: str) -> UndoResult:
        transaction = self._load_transaction(transaction_id)
        if transaction is None:
            raise HistoryError("The selected history transaction no longer exists.")

        latest = self.last_undoable()
        if latest is None or latest.transaction_id != transaction.transaction_id:
            raise HistoryError(
                "For safety, only the most recent non-undone rename transaction can be undone."
            )

        self._validate_undo(transaction)

        # Track successfully reversed steps so an unexpected mid-undo error can
        # be repaired back to the pre-undo state.
        reversed_steps: list[RenameStep] = []
        retained_dirs: list[Path] = []
        try:
            for step in reversed(transaction.steps):
                if step.kind in {"rename_file", "rename_dir"}:
                    assert step.source is not None
                    step.destination.rename(step.source)
                    reversed_steps.append(step)
                elif step.kind == "mkdir":
                    directory = step.destination
                    if directory.exists():
                        try:
                            directory.rmdir()
                            reversed_steps.append(step)
                        except OSError:
                            # Never remove user-added data. Leaving a now-extra
                            # directory behind is safer than treating it as an error.
                            retained_dirs.append(directory)
                else:
                    raise HistoryError(f"Unsupported history step: {step.kind}")
        except Exception as exc:
            try:
                _redo_steps(list(reversed(reversed_steps)))
            except Exception as repair_exc:
                raise HistoryError(
                    "Undo failed and automatic repair was incomplete. "
                    f"Undo error: {exc}. Repair error: {repair_exc}"
                ) from exc
            raise HistoryError(f"Undo failed; original state was restored: {exc}") from exc

        undone_at = int(time.time())
        with self._connect() as connection:
            connection.execute(
                "UPDATE transactions SET undone_at = ? WHERE transaction_id = ?",
                (undone_at, transaction.transaction_id),
            )

        updated = self._load_transaction(transaction.transaction_id) or transaction
        return UndoResult(
            transaction=updated,
            restored_pairs=tuple((new, old) for old, new in transaction.pairs),
            retained_directories=tuple(retained_dirs),
        )

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM transaction_steps")
            connection.execute("DELETE FROM transaction_pairs")
            connection.execute("DELETE FROM transactions")

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM transactions").fetchone()
        return int(row["count"] if row is not None else 0)

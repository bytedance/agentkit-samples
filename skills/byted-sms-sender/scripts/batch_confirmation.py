# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License").
"""Local confirmation records for batch task creation and launch."""

from __future__ import annotations

import contextlib
import getpass
import hashlib
import json
import os
import pathlib
import sqlite3
import stat
import tempfile
import time
from typing import Any, Dict, Iterator, Optional

import runtime_environment


DEBOUNCE_SECONDS = 60
# These server codes are returned before task persistence. System errors may
# include a failure after persistence and must remain an unknown outcome.
CREATE_REJECTION_CODES = frozenset({
    "1001", "1023", "PUBLIC_RESOURCE_NOT_ALLOWED", "PUBLIC_RESOURCE_RELATION_NOT_FOUND",
    "PUBLIC_RESOURCE_SIGNATURE_MISMATCH", "PUBLIC_RESOURCE_TEMPLATE_MISMATCH",
    "PUBLIC_RESOURCE_TEMPLATE_NOT_FOUND", "PUBLIC_RESOURCE_TEMPLATE_INELIGIBLE",
    "PUBLIC_RESOURCE_AMBIGUOUS", "PUBLIC_RESOURCE_CONTENT_REVIEW_FAILED",
})
TASK_FIELDS = frozenset(
    {"taskId", "subAccount", "taskName", "signature", "templateId", "templateName", "channelType", "status", "totalCount", "dupCount", "scheduled", "sendTime", "sendContent"}
)


class BatchConfirmationError(ValueError):
    def __init__(self, message: str, code: str, *, outcome_unknown: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.outcome_unknown = outcome_unknown


def default_state_directory() -> pathlib.Path:
    # The temp directory can be shared across users; the child is private and
    # stable across CLI processes. Neither credentials nor recipient lists live here.
    owner = hashlib.sha256(getpass.getuser().encode("utf-8")).hexdigest()[:16]
    return pathlib.Path(tempfile.gettempdir()) / ("volcengine-sms-{}-batch-{}".format(runtime_environment.NAME, owner))


class ConfirmationStore:
    """SQLite provides atomic local reservations across processes, not cloud idempotency."""

    def __init__(self, directory: Optional[pathlib.Path] = None) -> None:
        self.directory = pathlib.Path(directory) if directory is not None else default_state_directory()
        self.path = self.directory / "confirmations.sqlite3"

    @contextlib.contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.directory.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise OSError("state directory is not a directory")
            if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise OSError("state directory is not private")
            try:
                descriptor = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
            info = self.path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise OSError("state file is not a regular file")
            if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise OSError("state file is not private")
            connection = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute(
                "CREATE TABLE IF NOT EXISTS confirmations ("
                "digest TEXT PRIMARY KEY, scope TEXT NOT NULL, fingerprint TEXT NOT NULL, "
                "file_key TEXT NOT NULL, state TEXT NOT NULL, updated REAL NOT NULL, task_id TEXT)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS batch_tasks ("
                "scope TEXT NOT NULL, task_id TEXT NOT NULL, digest TEXT NOT NULL, "
                "summary TEXT NOT NULL, launch_state TEXT NOT NULL, snapshot_digest TEXT, "
                "PRIMARY KEY (scope, task_id))"
            )
            yield connection
        except (OSError, sqlite3.Error) as exc:
            raise BatchConfirmationError(
                "本地确认记录不可用，已停止自动提交", "local_confirmation_unavailable"
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    def save_preview(self, digest: str, scope: str, fingerprint: str, file_key: str) -> None:
        with self._connection() as connection:
            # A new upload has a new digest. Never reset an existing submission.
            connection.execute(
                "INSERT INTO confirmations (digest, scope, fingerprint, file_key, state, updated) "
                "VALUES (?, ?, ?, ?, 'preview', ?)",
                (digest, scope, fingerprint, file_key, time.time()),
            )

    def read_preview(self, digest: str, scope: str, fingerprint: str) -> Dict[str, Any]:
        with self._connection() as connection:
            record = connection.execute(
                "SELECT * FROM confirmations WHERE digest=? AND scope=? AND fingerprint=?",
                (digest, scope, fingerprint),
            ).fetchone()
        if record is None:
            raise BatchConfirmationError("输入、登录身份或确认记录已变化，请重新预览", "preview_changed")
        return dict(record)

    def reserve(self, digest: str, scope: str, fingerprint: str) -> Optional[str]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            record = connection.execute(
                "SELECT * FROM confirmations WHERE digest=? AND scope=? AND fingerprint=?",
                (digest, scope, fingerprint),
            ).fetchone()
            if record is None:
                raise BatchConfirmationError("确认记录已变化，请重新预览", "preview_changed")
            if record["state"] not in {"preview", "pending", "unknown", "created"}:
                raise BatchConfirmationError("本地提交状态无效，已停止自动提交", "local_confirmation_unavailable")
            if record["state"] == "created":
                if not record["task_id"]:
                    raise BatchConfirmationError("本地任务记录不完整，请先核对任务", "submission_outcome_unknown", outcome_unknown=True)
                connection.commit()
                return str(record["task_id"])
            prior = connection.execute(
                "SELECT * FROM confirmations WHERE fingerprint=? AND scope=? AND "
                "(state IN ('pending','unknown') OR (state='created' AND updated>?)) "
                "ORDER BY updated DESC LIMIT 1",
                (fingerprint, scope, time.time() - DEBOUNCE_SECONDS),
            ).fetchone()
            if prior is not None:
                if prior["state"] == "created":
                    if not prior["task_id"]:
                        raise BatchConfirmationError("本地任务记录不完整，请先核对任务", "submission_outcome_unknown", outcome_unknown=True)
                    connection.execute(
                        "UPDATE confirmations SET state='created', task_id=?, updated=? WHERE digest=?",
                        (prior["task_id"], time.time(), digest),
                    )
                    connection.commit()
                    return str(prior["task_id"])
                raise BatchConfirmationError(
                    "本次提交结果待确认，请先查询任务，勿重复提交",
                    "submission_outcome_unknown",
                    outcome_unknown=True,
                )
            connection.execute(
                "UPDATE confirmations SET state='pending', updated=? WHERE digest=?",
                (time.time(), digest),
            )
            connection.commit()
        return None

    def finish(self, digest: str, task_id: Optional[str]) -> None:
        with self._connection() as connection:
            updated = connection.execute(
                "UPDATE confirmations SET state=?, task_id=?, updated=? WHERE digest=? AND state='pending'",
                ("created" if task_id else "unknown", task_id, time.time(), digest),
            )
            if updated.rowcount != 1:
                raise BatchConfirmationError("本地提交记录已变化，请先查询任务", "submission_outcome_unknown", outcome_unknown=True)

    def discard_rejected(self, digest: str) -> None:
        """Consume the preview when dispatch or task creation is known not to have run."""
        with self._connection() as connection:
            connection.execute("DELETE FROM confirmations WHERE digest=? AND state='pending'", (digest,))

    def save_task(self, scope: str, task_id: str, digest: str, summary: Dict[str, Any]) -> None:
        """Persist only identifiers, counts and hashes for a created, unsent task."""
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO batch_tasks (scope, task_id, digest, summary, launch_state) "
                "VALUES (?, ?, ?, ?, 'ready') ON CONFLICT(scope, task_id) DO NOTHING",
                (scope, task_id, digest, json.dumps(summary, ensure_ascii=False, sort_keys=True)),
            )

    def task(self, scope: str, task_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT digest, summary, launch_state, snapshot_digest FROM batch_tasks WHERE scope=? AND task_id=?",
                (scope, task_id),
            ).fetchone()
        if row is None:
            raise BatchConfirmationError("缺少本地创建记录，请核对任务，不要重新创建", "batch_task_record_missing")
        return {"digest": row["digest"], "summary": json.loads(row["summary"]), "launchState": row["launch_state"], "snapshotDigest": row["snapshot_digest"]}

    def preview_launch(self, scope: str, task_id: str, digest: str, snapshot_digest: str) -> None:
        with self._connection() as connection:
            updated = connection.execute(
                "UPDATE batch_tasks SET digest=?, snapshot_digest=? "
                "WHERE scope=? AND task_id=? AND launch_state='ready'",
                (digest, snapshot_digest, scope, task_id),
            )
            if updated.rowcount != 1:
                raise BatchConfirmationError("确认请求已发出，请先核对同一任务", "submission_outcome_unknown", outcome_unknown=True)

    def reserve_launch(self, scope: str, task_id: str, digest: str) -> None:
        with self._connection() as connection:
            updated = connection.execute(
                "UPDATE batch_tasks SET launch_state='pending' "
                "WHERE scope=? AND task_id=? AND digest=? AND launch_state='ready'",
                (scope, task_id, digest),
            )
            if updated.rowcount != 1:
                raise BatchConfirmationError("确认结果待核对，请查询同一任务，勿重复提交", "submission_outcome_unknown", outcome_unknown=True)

    def finish_launch(self, scope: str, task_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE batch_tasks SET launch_state='confirmed' WHERE scope=? AND task_id=?",
                (scope, task_id),
            )

    def reject_launch(self, scope: str, task_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE batch_tasks SET launch_state='ready', snapshot_digest=NULL "
                "WHERE scope=? AND task_id=? AND launch_state='pending'",
                (scope, task_id),
            )

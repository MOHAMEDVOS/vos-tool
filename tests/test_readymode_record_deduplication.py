from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from automation import download_readymode_calls as downloader
from automation.readymode_http import canonical_dialer_host, normalize_recording_id
from backend.services import readymode_recording_registry as registry


def _initialize_registry_database(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DB_TYPE", "sqlite")

    from lib.database import DatabaseManager
    import backend.core.database as database_module

    db = DatabaseManager()
    monkeypatch.setattr(database_module, "_db_manager", db)
    database_module.run_database_migrations()


def test_registry_skips_audited_records_and_scopes_identity(monkeypatch, tmp_path):
    _initialize_registry_database(monkeypatch, tmp_path)
    identity = {"dialer_host": "resva.readymode.com", "recording_id": "/recording/one.mp3"}

    claimed = registry.claim_recordings(
        "auditor", identity["dialer_host"], [identity["recording_id"]], "run-1"
    )
    assert claimed == {identity["recording_id"]}
    assert registry.claim_recordings(
        "auditor", identity["dialer_host"], [identity["recording_id"]], "run-2"
    ) == set()

    assert registry.mark_recordings_audited("auditor", [identity], "run-1") == 1
    assert registry.claim_recordings(
        "auditor", identity["dialer_host"], [identity["recording_id"]], "run-3"
    ) == set()
    assert registry.claim_recordings(
        "auditor", identity["dialer_host"], [identity["recording_id"]], "run-4", True
    ) == {identity["recording_id"]}

    registry.release_recordings("auditor", [identity], "run-4")
    assert registry.claim_recordings(
        "auditor", identity["dialer_host"], [identity["recording_id"]], "run-5"
    ) == set()
    assert registry.claim_recordings(
        "another-auditor", identity["dialer_host"], [identity["recording_id"]], "run-6"
    ) == {identity["recording_id"]}
    assert registry.claim_recordings(
        "auditor", "resva2.readymode.com", [identity["recording_id"]], "run-7"
    ) == {identity["recording_id"]}

    failed_identity = {"dialer_host": "resva.readymode.com", "recording_id": "/recording/retry.mp3"}
    assert registry.claim_recordings(
        "auditor", failed_identity["dialer_host"], [failed_identity["recording_id"]], "run-8"
    ) == {failed_identity["recording_id"]}
    registry.release_recordings("auditor", [failed_identity], "run-8")
    assert registry.claim_recordings(
        "auditor", failed_identity["dialer_host"], [failed_identity["recording_id"]], "run-9"
    ) == {failed_identity["recording_id"]}


def test_recording_identity_removes_download_query_parameter():
    assert canonical_dialer_host("HTTPS://Resva.ReadyMode.com/") == "resva.readymode.com"
    assert normalize_recording_id("/recording/one.mp3?force_dl=1") == "/recording/one.mp3"
    assert normalize_recording_id("/recording/one.mp3?token=x&force_dl=1&region=ny") == (
        "/recording/one.mp3?region=ny&token=x"
    )


def test_audit_rows_keep_record_identity_and_retry_error_rows():
    import pandas as pd
    from backend.services.readymode_recording_metadata import (
        attach_recording_identity,
        recording_rows_from_dataframe,
    )

    first_file = "/tmp/run/first.mp3"
    failed_file = "/tmp/run/failed.mp3"
    manifest = {
        "records": [
            {
                "file_path": first_file,
                "dialer_host": "resva.readymode.com",
                "recording_id": "/recording/first.mp3",
            },
            {
                "file_path": failed_file,
                "dialer_host": "resva.readymode.com",
                "recording_id": "/recording/failed.mp3",
            },
        ]
    }
    source_df = pd.DataFrame(
        {"File Path": [first_file, failed_file], "Status": ["Excellent", "Error: transcription failed"]}
    )

    identified_df = attach_recording_identity(source_df, manifest)

    assert identified_df.iloc[0]["ReadyMode Recording ID"] == "/recording/first.mp3"
    assert recording_rows_from_dataframe(identified_df) == [
        {"dialer_host": "resva.readymode.com", "recording_id": "/recording/first.mp3"}
    ]


def test_downloader_does_not_download_a_recording_it_cannot_claim(monkeypatch, tmp_path):
    record = {
        "RecId": "/recording/already-audited.mp3?force_dl=1",
        "User": "Agent A",
        "Time": "05:00 PM",
        "Type": "Unknown",
        "File": "(212) 555-0100",
    }

    class FakeReadyModeClient:
        def __init__(self, dialer_url):
            self.dialer = dialer_url.rstrip("/")
            self.cookies = {}

        def login(self, username, password):
            return None

        def init_call_log(self):
            return {"unknown": "1"}

        def fetch_report(self, **kwargs):
            return {"pages": 1, "results": {"0": record}}

    import config

    monkeypatch.setattr(config, "RECORDINGS_ROOT", tmp_path / "Recordings")
    monkeypatch.setattr(downloader, "ReadyModeHTTPClient", FakeReadyModeClient)
    download_mock = Mock(return_value=(True, "unused", None))
    monkeypatch.setattr(downloader, "download_single_file", download_mock)

    result_dir = downloader.download_all_call_recordings(
        dialer_url="https://resva.readymode.com/",
        agent="All users",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 28),
        max_samples=1,
        username="auditor",
        readymode_user="ready-user",
        readymode_pass="ready-password",
        registry_run_id="run-1",
        claim_recordings_callback=lambda host, ids, run_id, force: set(),
        release_recordings_callback=lambda records, run_id: None,
    )

    manifest = json.loads((Path(result_dir) / ".readymode_manifest.json").read_text())
    assert manifest["skipped_count"] == 1
    assert manifest["records"] == []
    download_mock.assert_not_called()

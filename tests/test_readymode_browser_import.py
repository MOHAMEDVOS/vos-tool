import io
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import readymode


def test_browser_import_saves_recordings_for_existing_analysis(tmp_path, monkeypatch):
    import config
    import automation.download_readymode_calls as downloader

    monkeypatch.setattr(config, "RECORDINGS_ROOT", tmp_path)
    monkeypatch.setattr(config, "get_user_daily_limit", lambda _username: 10)
    monkeypatch.setattr(downloader, "_probe_duration_seconds", lambda _path: 60)
    monkeypatch.setattr(
        readymode,
        "_recording_registry_callbacks",
        lambda _username: (lambda _host, ids, _run_id, _force: set(ids), lambda *_args: None),
    )

    def analyze(download_path, _request, _user, _audit_type):
        folder = Path(download_path)
        audio_files = list(folder.glob("*.mp3"))
        manifest = json.loads((folder / ".readymode_manifest.json").read_text())
        assert len(audio_files) == 1
        assert manifest["records"][0]["recording_id"] == "/recordings/abc.mp3"
        return 1, 1, folder, 0

    monkeypatch.setattr(readymode, "_count_and_analyze", analyze)
    request = json.dumps({
        "dialer_url": "https://resva3.readymode.com/",
        "agent_name": "Nora Smith",
        "max_calls": 10,
        "start_date": "2026-10-28",
        "end_date": "2026-10-28",
        "audit_type": "heavy",
        "minimum_call_duration_seconds": 1,
    })
    manifest = json.dumps([{
        "dialer_host": "resva3.readymode.com",
        "recording_id": "/recordings/abc.mp3?force_dl=1",
        "filename": "Nora_Callback.mp3",
        "type": "Callback",
    }])

    app = FastAPI()
    app.include_router(readymode.router)
    app.dependency_overrides[readymode.get_current_user] = lambda: {
        "username": "test-user", "role": "Admin",
    }
    with TestClient(app) as client:
        response = client.post(
            "/browser-import",
            data={"audit_request": request, "manifest": manifest},
            files=[("files", ("Nora_Callback.mp3", io.BytesIO(b"fake mp3 data"), "audio/mpeg"))],
        )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["downloaded_count"] == 1
    assert response.json()["analyzed_count"] == 1

"""Attach ReadyMode source IDs to audit rows and find successfully processed records."""

from __future__ import annotations

import os


def attach_recording_identity(df, manifest: dict):
    """Copy stable source identity from the download manifest onto matching file rows."""
    if df is None or df.empty:
        return df

    path_to_identity = {
        os.path.normcase(os.path.abspath(record["file_path"])): record
        for record in manifest.get("records", [])
        if record.get("file_path") and record.get("recording_id") and record.get("dialer_host")
    }
    if not path_to_identity or "File Path" not in df.columns:
        return df

    result = df.copy()

    def find_identity(file_path):
        if not isinstance(file_path, (str, os.PathLike)) or not str(file_path).strip():
            return None
        return path_to_identity.get(os.path.normcase(os.path.abspath(str(file_path))))

    identities = result["File Path"].map(find_identity)
    result["ReadyMode Recording ID"] = identities.map(
        lambda identity: identity["recording_id"] if identity else ""
    )
    result["ReadyMode Dialer Host"] = identities.map(
        lambda identity: identity["dialer_host"] if identity else ""
    )
    return result


def recording_rows_from_dataframe(df) -> list[dict[str, str]]:
    """Return source IDs from saved rows, excluding analyzer error rows."""
    if df is None or df.empty:
        return []
    required = {"ReadyMode Recording ID", "ReadyMode Dialer Host"}
    if not required.issubset(df.columns):
        return []

    successful_rows = None
    if "Status" in df.columns:
        successful_rows = ~df["Status"].fillna("").astype(str).str.strip().str.lower().str.startswith("error")

    rows = []
    for index, (host, recording_id) in enumerate(
        zip(df["ReadyMode Dialer Host"], df["ReadyMode Recording ID"])
    ):
        if successful_rows is not None and not bool(successful_rows.iloc[index]):
            continue
        if isinstance(host, str) and host.strip() and isinstance(recording_id, str) and recording_id.strip():
            rows.append({"dialer_host": host, "recording_id": recording_id})
    return rows

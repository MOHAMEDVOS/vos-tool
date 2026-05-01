"""
One-time migration: move campaign audit rows out of agent_audit_results
and into campaign_audit_results.

Rows are identified by having a non-empty 'Campaign Name' in their metadata JSONB.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.database import get_db_manager
db = get_db_manager()

def run():
    # 1. Find all agent_audit_results rows that have Campaign Name in metadata
    rows = db.execute_query(
        "SELECT * FROM agent_audit_results ORDER BY created_at ASC",
        fetch=True,
    )
    if not rows:
        print("No rows in agent_audit_results.")
        return

    campaign_groups: dict[tuple, list] = {}  # (campaign_name, username) -> [records]

    agent_ids_to_delete = []

    for row in rows:
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        campaign_name = meta.get("Campaign Name") or ""
        if not campaign_name.strip():
            continue  # not a campaign row — leave it

        username = row.get("username", "")
        key = (campaign_name.strip(), username)

        # Reconstruct a record dict the same way save_campaign_audit_results expects
        record = {
            "Agent Name":          row.get("agent_name"),
            "File Name":           row.get("file_name"),
            "File Path":           row.get("file_path"),
            "Releasing Detection": row.get("releasing_detection"),
            "Late Hello Detection":row.get("late_hello_detection"),
            "Rebuttal Detection":  row.get("rebuttal_detection"),
            "Timestamp":           str(row.get("timestamp") or ""),
            "Call Duration":       row.get("call_duration"),
            "Transcription":       row.get("transcript", ""),
            "Confidence Score":    row.get("confidence_score"),
            "Feedback":            row.get("feedback"),
            "username":            username,
        }
        record.update(meta)  # pull everything from metadata (Dialer Name, etc.)

        campaign_groups.setdefault(key, []).append(record)
        agent_ids_to_delete.append(row["id"])

    if not agent_ids_to_delete:
        print("No campaign rows found in agent_audit_results. Nothing to migrate.")
        return

    print(f"Found {len(agent_ids_to_delete)} campaign rows across {len(campaign_groups)} campaign(s).")

    # 2. Insert each group into campaign_audit_results
    import datetime
    for (campaign_name, username), records in campaign_groups.items():
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        record_count    = len(records)
        releasing_count = sum(1 for r in records if r.get("Releasing Detection") == "Yes")
        late_hello_count= sum(1 for r in records if r.get("Late Hello Detection") == "Yes")
        rebuttal_count  = sum(1 for r in records if r.get("Rebuttal Detection")  == "Yes")

        metadata = {
            "campaign_name": campaign_name,
            "username":      username,
            "timestamp":     timestamp,
            "data":          records,
        }

        db.execute_query(
            """
            INSERT INTO campaign_audit_results
              (campaign_name, username, timestamp, record_count,
               releasing_count, late_hello_count, rebuttal_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                campaign_name, username, timestamp,
                record_count, releasing_count, late_hello_count, rebuttal_count,
                json.dumps(metadata, default=str),
            ),
            fetch=False,
        )
        print(f"  ✓ Migrated '{campaign_name}' ({username}): {record_count} records")

    # 3. Delete the migrated rows from agent_audit_results
    placeholders = ",".join(["%s"] * len(agent_ids_to_delete))
    db.execute_query(
        f"DELETE FROM agent_audit_results WHERE id IN ({placeholders})",
        tuple(agent_ids_to_delete),
        fetch=False,
    )
    print(f"\n✓ Deleted {len(agent_ids_to_delete)} rows from agent_audit_results.")
    print("Migration complete.")

if __name__ == "__main__":
    run()

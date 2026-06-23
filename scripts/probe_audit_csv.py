"""Probe: discover ReadyMode CSV field keys + export the "audit" CSV for today.

Run from the repo root:
  python scripts/probe_audit_csv.py

What it does:
  1. Logs into resva2 (change DIALER below if needed)
  2. Fetches the export dialog HTML -> lists ALL available fieldKey values
  3. Tries to export a CSV with the audit columns (Agent, Phone, Disposition,
     Recording Length, Campaign) for today
  4. Prints the first 10 rows so we can confirm column names
"""

import sys
import os
from pathlib import Path
from datetime import date

# ── repo root on sys.path ────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.readymode_http import ReadyModeHTTPClient

# ── config — change if needed ────────────────────────────────────────────────
DIALER   = os.getenv("PROBE_DIALER",   "https://resva2.readymode.com")
RM_USER  = os.getenv("READYMODE_USER",  "")
RM_PASS  = os.getenv("READYMODE_PASSWORD", "")

if not RM_USER or not RM_PASS:
    # Try loading from .env if present
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        RM_USER = os.getenv("READYMODE_USER", "")
        RM_PASS = os.getenv("READYMODE_PASSWORD", "")

if not RM_USER or not RM_PASS:
    print("ERROR: Set READYMODE_USER and READYMODE_PASSWORD env vars (or in .env)")
    sys.exit(1)

TODAY = date.today().strftime("%m/%d/%Y")

print(f"Dialer : {DIALER}")
print(f"Date   : {TODAY}")
print(f"User   : {RM_USER}")
print()

client = ReadyModeHTTPClient(DIALER)

# ── Step 1: login ────────────────────────────────────────────────────────────
print("Step 1: Login...")
client.login(RM_USER, RM_PASS)
print("  ✓ stationId cookie present")

# ── Step 2: probe export dialog for ALL available fieldKey values ─────────────
print("\nStep 2: Fetch export dialog -> list all fieldKey values...")
try:
    import re
    r = client.session.get(
        f"{DIALER}/CCS Reports/call_log/ExportMenu",
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{DIALER}/",
        },
        timeout=30,
    )
    html = r.text or ""
    # fieldKey is in <li fieldKey="..."> or <li data-field-key="..."> elements
    keys_from_li = re.findall(r'fieldKey=["\']([^"\']+)["\']', html)
    # also try data attributes
    keys_from_data = re.findall(r'data-field-key=["\']([^"\']+)["\']', html)
    # and any label/name pairs
    labels = re.findall(r'<li[^>]*fieldKey=["\']([^"\']+)["\'][^>]*>\s*([^<]+)', html)

    all_keys = list(dict.fromkeys(keys_from_li + keys_from_data))  # dedupe, preserve order

    if all_keys:
        print(f"  Found {len(all_keys)} field keys:")
        for fk in all_keys:
            # find matching label if available
            lbl = next((l for k, l in labels if k == fk), "")
            print(f"    {fk:<40}  {lbl.strip()}")
    else:
        print("  No fieldKey attributes found in dialog HTML.")
        print(f"  HTML snippet (first 500 chars): {html[:500]}")

    # Also check for named templates we can load
    template_ids = re.findall(r'load_ajax\?id=(\d+)', html)
    if template_ids:
        print(f"\n  Template IDs in dialog: {template_ids}")
        # Load the widest template (highest id usually has most fields)
        for tid in template_ids[:3]:
            tr = client.session.get(
                f"{DIALER}/CCS Reports/call_log/ExportMenu/load_ajax?id={tid}",
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{DIALER}/"},
                timeout=15,
            )
            print(f"  Template {tid}: {tr.text[:300]}")

except Exception as e:
    print(f"  Dialog probe failed: {e}")

# ── Step 3: seed report state (all dispositions, today) ──────────────────────
print("\nStep 3: Seed report filter (all dispositions, today)...")
client.init_call_log()
report = client.fetch_report(time_from=TODAY, time_to=TODAY, page=0)
total_pages = report.get("pages", 0)
sample_row = next(iter((report.get("results") or {}).values()), None)
print(f"  Pages: {total_pages}")
if sample_row:
    print(f"  Sample JSON row keys: {list(sample_row.keys())}")
    print(f"  Sample row: {sample_row}")

# ── Step 4: export audit CSV with candidate field keys ───────────────────────
print("\nStep 4: Export audit CSV...")

# The "audit" CSV needs: Agent, Phone, Disposition, Recording Length, Campaign
# We'll try the most likely ReadyMode field keys for the columns we don't know yet.
AUDIT_FIELDS = [
    ("u.u_name",           "Agent Name"),
    ("CCS_Profile.phone",  "Phone Number"),
    ("Log Type",           "Disposition"),           # candidate
    ("CCS.dis_name",       "Disposition_alt1"),      # candidate
    ("dis_name",           "Disposition_alt2"),      # candidate
    ("CCS.call_length",    "Recording Length (Seconds)"),  # candidate
    ("call_length",        "RecLen_alt1"),            # candidate
    ("CCS.u_call_length",  "RecLen_alt2"),            # candidate
    ("campaign.campaign_name", "Current campaign"),  # candidate
    ("CCS.campaign_name",  "Campaign_alt1"),          # candidate
    ("campaign_name",      "Campaign_alt2"),          # candidate
    ("Log Time",           "Log Time"),               # known from spec
    ("Call Log ID",        "Call Log ID"),            # known from spec
]

try:
    csv_bytes = client.export_call_log_csv(
        time_from=TODAY, time_to=TODAY,
        fields=AUDIT_FIELDS,
    )
    print(f"  ✓ CSV downloaded ({len(csv_bytes)} bytes)")

    # Save to file
    out_path = Path(__file__).parent.parent / "scratch" / "probe_audit_output.csv"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_bytes(csv_bytes)
    print(f"  Saved to: {out_path}")

    # Print first 10 rows
    import csv, io
    text = csv_bytes.decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    print(f"\n  Header row: {rows[0] if rows else 'EMPTY'}")
    print(f"  Total rows (incl. header): {len(rows)}")
    if len(rows) > 1:
        print("\n  First 5 data rows:")
        for row in rows[1:6]:
            print(f"    {row}")

except Exception as e:
    print(f"  CSV export failed: {e}")

print("\nDone.")

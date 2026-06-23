"""Probe: find the ReadyMode CSV fieldKey for campaign name.

We already know:
  u.u_name          -> Agent Name      ✓
  CCS_Profile.phone -> Phone Number    ✓
  Log Type          -> Disposition     ✓
  CCS.call_length   -> Recording Length (Seconds) ✓
  campaign ???      -> Current campaign (UNKNOWN — this probe finds it)

Run:
  python scripts/probe_campaign_field.py [dialer_url]

Examples:
  python scripts/probe_campaign_field.py
  python scripts/probe_campaign_field.py https://resva6.readymode.com
"""

import sys, os, csv, io
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── load .env if present ────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

DIALER  = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PROBE_DIALER", "https://resva2.readymode.com")
RM_USER = os.getenv("READYMODE_USER", "").strip()
RM_PASS = os.getenv("READYMODE_PASSWORD", "").strip()

# ── try pulling creds from VOS DB (owner account) if not set via env ─────────
if not RM_USER or not RM_PASS:
    try:
        from config import get_user_readymode_credentials
        owner_email = "mohamedibrahimpayonner@gmail.com"
        rm_u, rm_p = get_user_readymode_credentials(owner_email)
        if rm_u and rm_p:
            RM_USER, RM_PASS = rm_u, rm_p
            print(f"Using DB credentials for {owner_email}: user={RM_USER}")
    except Exception as e:
        print(f"Could not load DB credentials: {e}")

if not RM_USER or not RM_PASS:
    print("ERROR: No ReadyMode credentials found.")
    print("Set READYMODE_USER and READYMODE_PASSWORD env vars, or ensure the owner account has ReadyMode creds in the DB.")
    sys.exit(1)

TODAY = date.today().strftime("%m/%d/%Y")
print(f"Dialer : {DIALER}")
print(f"Date   : {TODAY}")
print(f"RM User: {RM_USER}\n")

from automation.readymode_http import ReadyModeHTTPClient

client = ReadyModeHTTPClient(DIALER)
client.login(RM_USER, RM_PASS)
print("✓ Logged in\n")

# Seed report + grab a sample JSON row to see what keys ReadyMode sends
client.init_call_log()
report = client.fetch_report(time_from=TODAY, time_to=TODAY, page=0)
total_pages = report.get("pages", 0)
results = report.get("results") or {}
sample = next(iter(results.values()), None)
print(f"Total pages today: {total_pages}")
if sample:
    print(f"Sample JSON row (all keys): {list(sample.keys())}")
    print(f"Sample row: {sample}\n")
else:
    print("No calls today on this dialer — trying yesterday's date\n")
    from datetime import timedelta
    yesterday = (date.today() - timedelta(days=1)).strftime("%m/%d/%Y")
    report = client.fetch_report(time_from=yesterday, time_to=yesterday, page=0)
    results = report.get("results") or {}
    sample = next(iter(results.values()), None)
    if sample:
        TODAY = yesterday
        print(f"Using yesterday ({yesterday}), pages={report.get('pages')}")
        print(f"Sample JSON row: {sample}\n")
    else:
        print("No data yesterday either. Can't probe.")
        sys.exit(0)

# ── campaign candidate field keys ───────────────────────────────────────────
CAMPAIGN_CANDIDATES = [
    "campaign_name",
    "campaign.campaign_name",
    "campaign.name",
    "CCS.campaign",
    "CCS.campaign_name",
    "CCS_Campaign.campaign_name",
    "CCS_Campaign.name",
    "CCS_List.list_name",
    "list_name",
    "CCS.list_name",
    "CCS_Profile.list",
    "CCS.batch",
    "batch_name",
]

FIELDS = (
    [
        ("u.u_name",          "Agent Name"),
        ("CCS_Profile.phone", "Phone Number"),
        ("Log Type",          "Disposition"),
        ("CCS.call_length",   "Recording Length (Seconds)"),
    ]
    + [(k, f"CAMP_{i}") for i, k in enumerate(CAMPAIGN_CANDIDATES)]
)

print(f"Exporting CSV with {len(FIELDS)} fields ({len(CAMPAIGN_CANDIDATES)} campaign candidates)...")
csv_bytes = client.export_call_log_csv(time_from=TODAY, time_to=TODAY, fields=FIELDS)
print(f"✓ CSV received ({len(csv_bytes)} bytes)\n")

text  = csv_bytes.decode("utf-8", errors="replace")
rows  = list(csv.reader(io.StringIO(text)))
header = rows[0] if rows else []
print(f"Header: {header}\n")

if len(rows) < 2:
    print("No data rows — can't check candidates")
    sys.exit(0)

print("Campaign candidate results:")
print("-" * 65)
for i, key in enumerate(CAMPAIGN_CANDIDATES):
    col_label = f"CAMP_{i}"
    try:
        col_idx = header.index(col_label)
    except ValueError:
        print(f"  {key:<42}  [not in CSV]")
        continue
    sample_val = next(
        (row[col_idx] for row in rows[1:] if col_idx < len(row) and row[col_idx].strip()),
        None
    )
    marker = f"✓  VALUE: {sample_val!r}" if sample_val else "(empty)"
    print(f"  {key:<42}  {marker}")

# Show first 3 data rows with the known-good columns
print("\nFirst 3 data rows (known columns only):")
for row in rows[1:4]:
    print(f"  Agent={row[0]!r:30}  Disp={row[2]!r:20}  Len={row[3]!r}")

out = Path(__file__).parent.parent / "scratch" / "probe_campaign_output.csv"
out.parent.mkdir(exist_ok=True)
out.write_bytes(csv_bytes)
print(f"\nFull CSV saved → {out}")

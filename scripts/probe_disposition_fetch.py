"""Live read-only check: filter resv5 by the user's 8 dispositions and tally what
disposition ('Type') actually comes back. Pulls a few report pages only; downloads
nothing, changes nothing.

Tests three filters to localise where 'Voicemail' leaks in:
  A) the 8 picks resolved via resv5's live map (what the app actually sends)
  B) the same MINUS 'Not logged' (isolates the id -1 wildcard theory)
  C) only 'Not logged' (id -1) on its own
"""
import sys
from collections import Counter
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.readymode_http import ReadyModeHTTPClient, disposition_type_ids

CREATE_USER = "UserCreation"
CREATE_PASS = "RES370@370"
DIALER = "https://resva5.readymode.com/"

WANTED = ["Spanish Speaker", "DNC - Unknown", "Unknown", "DNC - Decision Maker",
          "Wrong Number", "Decision Maker - NYI", "Dead Call", "Not logged"]
WANTED_NO_NOTLOGGED = WANTED[:-1]

# wide date window so there are rows to inspect
TIME_FROM = "2026-06-01"
TIME_TO = date.today().isoformat()


def tally(client, types, label, max_pages=4):
    print(f"\n--- {label}\n    types sent: {types}")
    c = Counter()
    total = 0
    for page in range(max_pages):
        data = client.fetch_report(time_from=TIME_FROM, time_to=TIME_TO,
                                   types=types, page=page)
        results = data.get("results") or {}
        if not results:
            break
        for row in results.values():
            c[(row.get("Type") or "??").strip()] += 1
            total += 1
    print(f"    rows sampled: {total}")
    for disp, n in c.most_common():
        flag = "   <<< VOICEMAIL LEAKED" if "voicemail" in disp.lower() else ""
        print(f"        {n:>4}  {disp}{flag}")
    return c


client = ReadyModeHTTPClient(DIALER)
client.login(CREATE_USER, CREATE_PASS)
print("login OK on resva5")
dmap = client.init_call_log()

types_all = disposition_type_ids(WANTED, dmap)
types_no_nl = disposition_type_ids(WANTED_NO_NOTLOGGED, dmap)
types_only_nl = disposition_type_ids(["Not logged"], dmap)

tally(client, types_all, "A) user's 8 picks (as the app sends them)")
tally(client, types_no_nl, "B) 8 picks MINUS 'Not logged'")
tally(client, types_only_nl, "C) only 'Not logged' (id -1)")

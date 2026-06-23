"""Validate the resv5 'voicemail' disposition bug (read-only, creates/changes nothing).

For each dialer it:
  1. logs in,
  2. calls init_call_log() to fetch THAT dialer's own live label->id map,
  3. reports whether the live map came back EMPTY (=> code falls back to the
     resva2-captured static guess, which is wrong on other dialers),
  4. reverse-maps the STATIC fallback ids to what they REALLY mean on this dialer,
  5. shows how the user's requested labels resolve (live map vs static fallback).

If resv5's live map is empty, the user's picks get resolved with resva2 ids, and
those ids point at different dispositions on resv5 (e.g. Voicemail).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.readymode_http import (
    ReadyModeHTTPClient, disposition_type_ids,
    DISPOSITION_TYPE_IDS, BASE_TYPE,
)

CREATE_USER = "UserCreation"
CREATE_PASS = "RES370@370"

# what the user said they pick on resv5
WANTED = [
    "Spanish Speaker", "DNC - Unknown", "Unknown", "DNC - Decision Maker",
    "Wrong Number", "Decision Maker - NYI", "Dead Call", "Not logged",
]

DIALERS = ["resva2", "resva5"]  # resva2 = control (static map was captured here)
URLS = {n: f"https://{n}.readymode.com/" for n in DIALERS}


def reverse(dmap):
    """id(str) -> label, from this dialer's own live map."""
    return {str(v): k for k, v in dmap.items()}


for name in DIALERS:
    print("=" * 78)
    print(name.upper())
    print("=" * 78)
    client = ReadyModeHTTPClient(URLS[name])
    try:
        client.login(CREATE_USER, CREATE_PASS)
        print("login OK")
    except Exception as e:
        print(f"login FAILED: {e}")
        continue

    dmap = client.init_call_log()
    print(f"live disposition map size: {len(dmap)}  "
          f"{'<<< EMPTY -> code uses STATIC fallback' if not dmap else ''}")
    if dmap:
        for label, v in sorted(dmap.items(), key=lambda kv: str(kv[1])):
            print(f"    id {str(v):>4}  = {label}")

    rev = reverse(dmap)

    print("\n  What the resva2 STATIC ids actually point at on this dialer:")
    for label, sid in DISPOSITION_TYPE_IDS.items():
        really = rev.get(str(sid), "??? (id not present on this dialer)")
        flag = "  <-- becomes VOICEMAIL" if "voicemail" in really.lower() else ""
        print(f"    static '{label}' -> id {sid:>4} -> really '{really}'{flag}")

    print("\n  User picks resolved WITH live map :",
          disposition_type_ids(WANTED, dmap) if dmap else "(no live map)")
    print("  User picks resolved with STATIC   :",
          disposition_type_ids(WANTED, None))
    print()

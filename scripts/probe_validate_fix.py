"""Validate the new dynamic folder resolution on every dialer. Creates nothing.

Exercises ReadyModeHTTPClient.resolve_folder('Agents') against resva..resva7 and
checks it returns each dialer's known per-instance id.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.readymode_http import ReadyModeHTTPClient

CREATE_USER = "UserCreation"
CREATE_PASS = "RES370@370"

EXPECTED = {
    "resva":  "48-36-14",  "resva2": "48-36-14", "resva3": "48-36-14",
    "resva4": "54-109-",   "resva5": "54-105-14",
    "resva6": "48-36-4",   "resva7": "48-36-4",
}
URLS = {n: f"https://{n}.readymode.com/" for n in EXPECTED}

ok = True
for name, url in URLS.items():
    client = ReadyModeHTTPClient(url)
    client.login(CREATE_USER, CREATE_PASS)
    got = client.resolve_folder("Agents")
    exp = EXPECTED[name]
    mark = "OK " if got == exp else "!! "
    if got != exp:
        ok = False
    print(f"  {mark}{name:<8} resolve_folder('Agents') -> {got}  (expected {exp})")

print("\nALL MATCH" if ok else "\nMISMATCH — review")

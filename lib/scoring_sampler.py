"""Per-agent call sampling for the Scoring section.

Pure, dependency-free functions (stdlib only) so they're easy to unit-test. This mirrors the
Google Apps Script "CSV Call Sampler" the user ran by hand, plus the flag-driven behaviour:

  * For an agent WITH flagged calls (releasing / late hello / no rebuttals, as detected by VOS),
    the scoring rows are that agent's flagged numbers, each carrying its flag type(s).
  * For an agent with NO flags, fall back to 5 random numbers from the dialer where the agent has
    the most calls (the "busiest dialer"), exactly like the Apps Script.

Agent-name matching mirrors ``automation/readymode_http.resolve_agent_id``: exact (case-insensitive)
first, then a ``name.``-prefix match.
"""

import re
import random
from collections import defaultdict

# Header alias maps copied from the user's Apps Script so the CSV parser tolerates whatever the
# ReadyMode export happens to name its columns.
_NAME_ALIASES = ["name", "agent name", "agentname", "agent", "user", "rep", "full name", "fullname"]
_PHONE_ALIASES = ["phonenumber", "phone", "phone number", "number", "to", "contact number", "ani", "clid"]

# Flag labels — order is the display order in the Note column.
FLAG_RELEASING = "Releasing"
FLAG_LATE_HELLO = "Late Hello"
FLAG_NO_REBUTTALS = "No Rebuttals"
_FLAG_ORDER = [FLAG_RELEASING, FLAG_LATE_HELLO, FLAG_NO_REBUTTALS]

DEFAULT_NUM_SAMPLES = 5
DEFAULT_RED_FLAG_THRESHOLD = 5


def _norm_key(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def normalize_digits(s) -> str:
    """Return a 10-digit US number, or '' if it can't be normalized (mirrors normalizeDigits_)."""
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) == 11 and d.startswith("1"):
        return d[1:]
    if len(d) == 10:
        return d
    return ""


def format_phone_us(digits: str) -> str:
    """'(xxx) xxx-xxxx' for a 10-digit string; pass through otherwise (mirrors formatPhoneUS_)."""
    if not digits:
        return ""
    if len(digits) != 10:
        return digits
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"


def parse_phone_agent_csv(csv_bytes) -> list:
    """Parse a ReadyMode export into ``[(agent, phone), ...]``.

    Uses header-alias detection (not fixed positions) and tolerates the trailing-comma quirk
    documented in ``docs/READYMODE_HTTP_SPEC.md §7`` (extra empty trailing column).
    """
    import csv
    import io

    text = csv_bytes.decode("utf-8", errors="replace") if isinstance(csv_bytes, (bytes, bytearray)) else str(csv_bytes)
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []

    header = [_norm_key(h) for h in rows[0]]
    name_aliases = {_norm_key(a) for a in _NAME_ALIASES}
    phone_aliases = {_norm_key(a) for a in _PHONE_ALIASES}

    def _find(aliases):
        for i, h in enumerate(header):
            if h in aliases:
                return i
        return -1

    name_idx = _find(name_aliases)
    phone_idx = _find(phone_aliases)
    if name_idx == -1 or phone_idx == -1:
        return []

    out = []
    for row in rows[1:]:
        if name_idx >= len(row) or phone_idx >= len(row):
            continue
        agent = str(row[name_idx]).strip()
        phone = str(row[phone_idx]).strip()
        if agent and phone:
            out.append((agent, phone))
    return out


def build_agent_index(records_by_dialer: dict) -> dict:
    """``{dialer: [(agent, phone), ...]}`` -> ``{agent_lower: {dialer: [phone, ...]}}``."""
    index = defaultdict(lambda: defaultdict(list))
    for dialer, records in (records_by_dialer or {}).items():
        for agent, phone in records:
            index[agent.strip().lower()][dialer].append(phone)
    # plain dicts for JSON/Redis friendliness
    return {a: dict(d) for a, d in index.items()}


def flags_for_call(call: dict) -> list:
    """Which flags a single flagged-call row tripped (mirrors ActionsPage issue logic)."""
    flags = []
    if str(call.get("Releasing Detection", "")).strip() == "Yes":
        flags.append(FLAG_RELEASING)
    if str(call.get("Late Hello Detection", "")).strip() == "Yes":
        flags.append(FLAG_LATE_HELLO)
    if str(call.get("Rebuttal Detection", "")).strip() == "No":
        flags.append(FLAG_NO_REBUTTALS)
    return flags


def build_flagged_index(flagged_calls: list) -> dict:
    """``get_flagged_calls`` rows -> ``{agent_lower: [{phone, flags, dialer}, ...]}``.

    One entry per flagged CALL (so ``len`` matches the Actions-tab flagged count / red-flag rule).
    """
    index = defaultdict(list)
    for call in flagged_calls or []:
        agent = str(call.get("Agent Name", "")).strip()
        if not agent:
            continue
        index[agent.lower()].append({
            "phone": str(call.get("Phone Number", "")).strip(),
            "flags": flags_for_call(call),
            "dialer": str(call.get("Dialer Name", "")).strip(),
        })
    return dict(index)


def _match_key(keys, name: str):
    """Exact case-insensitive match, then ``name.``-prefix (mirrors resolve_agent_id)."""
    t = (name or "").strip().lower()
    if not t:
        return None
    if t in keys:
        return t
    for k in keys:
        if k == t or k.startswith(t + "."):
            return k
    return None


def _sample_random(dialer_map: dict, n: int):
    """Pick the busiest dialer, dedupe by 10-digit number, sample up to n, format. -> (phones, dialer)."""
    if not dialer_map:
        return [], ""
    best_dialer = max(dialer_map, key=lambda d: len(dialer_map[d]))
    seen = set()
    valid = []
    for raw in dialer_map[best_dialer]:
        d = normalize_digits(raw)
        if d and d not in seen:
            seen.add(d)
            valid.append(format_phone_us(d))
    if len(valid) <= n:
        sample = valid
    else:
        sample = random.sample(valid, n)
    return sample, best_dialer


def _note_from_flags(flag_set) -> str:
    ordered = [f for f in _FLAG_ORDER if f in flag_set]
    return ", ".join(ordered) if ordered else "Flagged"


def score_agents(rand_index: dict, flagged_index: dict, agent_names: list,
                 n: int = DEFAULT_NUM_SAMPLES,
                 red_flag_threshold: int = DEFAULT_RED_FLAG_THRESHOLD) -> dict:
    """Build the scoring table.

    Returns ``{"rows": [...], "skipped": [...]}``. Rows are in the pasted order; agents with no
    data in either index are skipped (like the Apps Script). Each row::

        {agent, phones: [{phone, flags}], note, flagged_count, red_flag, source, dialer}
    """
    rand_index = rand_index or {}
    flagged_index = flagged_index or {}
    rand_keys = set(rand_index.keys())
    flagged_keys = set(flagged_index.keys())

    rows = []
    skipped = []
    for raw_name in agent_names or []:
        name = str(raw_name).strip()
        if not name:
            continue

        # An agent is treated as "flagged" only when they have >= threshold flagged calls.
        # Fewer than that → the flags are ignored and the agent is sampled like a clean one
        # (5 random). This makes the flag threshold also gate flagged-vs-random sampling.
        fk = _match_key(flagged_keys, name)
        calls = flagged_index[fk] if fk else []
        if len(calls) >= red_flag_threshold:
            # dedupe by normalized number, merging the flags seen across that number's calls
            by_number = {}
            order = []
            all_flags = set()
            for c in calls:
                all_flags.update(c.get("flags") or [])
                d = normalize_digits(c.get("phone"))
                if not d:
                    continue
                if d not in by_number:
                    by_number[d] = set()
                    order.append(d)
                by_number[d].update(c.get("flags") or [])
            phones = [
                {"phone": format_phone_us(d),
                 "flags": [f for f in _FLAG_ORDER if f in by_number[d]]}
                for d in order
            ]
            dialers = sorted({c.get("dialer", "") for c in calls if c.get("dialer")})
            rows.append({
                "agent": name,
                "phones": phones,
                "note": _note_from_flags(all_flags),
                "flag_types": [f for f in _FLAG_ORDER if f in all_flags],
                "flagged_count": len(calls),
                "red_flag": len(calls) >= red_flag_threshold,
                "source": "flagged",
                "dialer": ", ".join(dialers),
            })
            continue

        rk = _match_key(rand_keys, name)
        if rk:
            sample, dialer = _sample_random(rand_index[rk], n)
            if not sample:
                skipped.append(name)
                continue
            rows.append({
                "agent": name,
                "phones": [{"phone": p, "flags": []} for p in sample],
                "note": "Clean",
                "flag_types": [],
                "flagged_count": 0,
                "red_flag": False,
                "source": "random",
                "dialer": dialer,
            })
            continue

        skipped.append(name)

    return {"rows": rows, "skipped": skipped}

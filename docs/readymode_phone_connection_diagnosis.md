# ReadyMode Softphone "Stuck on Preparing Connection" — Root-Cause Diagnosis

**Date:** 2026-06-18
**Investigated by:** automated, instrumented browser capture (Playwright + real Chromium)
**Test account:** `RES-1245`  •  **Tenant:** `resva7` (`https://resva7.readymode.com`)
**Status:** Root cause identified with high confidence → **ReadyMode server-side (PBX) SIP credential mismatch.** Not a client/network problem.

---

## TL;DR

The browser softphone connects to ReadyMode perfectly at every layer **except one**: the SIP
registration to ReadyMode's Asterisk PBX is **rejected with `401 Unauthorized` on every attempt**,
even after the phone correctly answers the authentication challenge.

- The phone's **app/event channel** (`wss://…:8079/calls`) is **fully connected** — agent presence,
  keep-alives, and messaging all work. → this is the *"connected"* half.
- The phone's **voice channel** (SIP REGISTER over `wss://…:5013/ws` to Asterisk) **never registers**
  → this is the missing half. The UI literally reports **"You're only half connected."**
- Because SIP never registers, the phone loops forever on **"Preparing connection"** and never
  reaches **Connected**, so the agent can't make/receive calls.

**48 REGISTER attempts → 48 × `401 Unauthorized` → 0 × `200 OK`.** The SIP secret ReadyMode injects
into this agent's phone does **not match** the secret on its PBX. Only ReadyMode can fix it
(re-provision the extension's SIP password). No amount of client-side troubleshooting (browser, VPN,
firewall, headset, Windows, cache) will help — and that explains why a week of IT troubleshooting did not.

---

## How the test was run (so results are trustworthy)

A real Chromium browser was driven with full instrumentation hooks injected *before* any ReadyMode
script ran, capturing every relevant layer:

| Layer | How it was captured |
|---|---|
| HTTP | every response ≥ 400, every failed request (`requestfailed`) |
| WebSocket | every socket open/close + **every frame payload** (SIP is text over WS) |
| WebRTC | `RTCPeerConnection` lifecycle, ICE states, candidates, `getStats()` |
| Microphone | `getUserMedia()` calls + errors |
| JavaScript | all console output + uncaught page errors |
| UI | phone status text, polled every 3s with timestamps |

Deliberate controls to remove false variables:
- Microphone was **granted + faked** (`--use-fake-device-for-media-stream`) so a missing/blocked mic
  could never be the cause — isolating the connection logic from hardware.
- Run from the **owner's machine on a different connection** than the affected agents. If the problem
  were the agents' local network, it would *not* reproduce here. **It reproduced identically.**

Observation window: ~90s after login (the phone retries REGISTER every ~1–2s, so this is dozens of cycles).

---

## What was observed

### Environment fingerprint
- **Phone client:** `xwsphone 0.7.2` (ReadyMode's WebRTC phone, SIP-over-WebSocket)
- **SIP / media backend:** `1-8-phx.xensub.net` (`xensub.net` = ReadyMode/XenCall telephony backend)
  - port **5013** → SIP signaling over WSS (`/ws`)
  - port **8079** → ReadyMode app/event channel over WSS (`/calls`)
- **PBX:** `Server: Asterisk PBX certified-20.7-cert4`
- **SIP endpoint (extension):** `28850-20026`, **realm:** `asterisk`
- **Agent public IP seen by server:** `received=41.235.200.79` (Egypt / TE Data)

### Layer-by-layer results

| Layer | Result | Verdict |
|---|---|---|
| DNS / TLS / login to `resva7.readymode.com` | Succeeded; app loaded; agent session active | ✅ fine |
| HTTP responses ≥ 400 | **0** | ✅ no server/HTTP/auth/CORS errors |
| Failed HTTP requests | 3, all benign (Cloudflare `cdn-cgi/rum` analytics beacon aborts + 1 `update.json` abort during a phone re-init) | ✅ irrelevant |
| JavaScript page errors | **0** | ✅ no JS crash |
| App/event WebSocket (`:8079/calls`) | **OPEN & active** — `KeepAlive`, `IM.Ping`, `ShareProf`, presence all flowing | ✅ ReadyMode app layer healthy |
| SIP WebSocket (`:5013/ws`) | **OPEN** (TLS handshake + WS upgrade fine) | ✅ transport fine |
| STUN (NAT traversal) | **Multiple successes** (`stun.l.google.com`, `stun.cloudflare.com`, others) | ✅ network/UDP/NAT fine |
| `getUserMedia` (microphone) | Not a factor (faked); never reached | ✅ mic ruled out |
| `RTCPeerConnection` | **Never created** — no call/media ever attempted | ⚠️ blocked upstream |
| **SIP REGISTER** | **48 sent → 48 × `401 Unauthorized` → 0 × `200 OK`** | ❌ **THE FAILURE** |
| UI phone status | Oscillates `"You're only half connected"` ↔ `"Preparing connection"`, **never `Connected`** | ❌ symptom |

> Note: `RTCPeerConnection` is never even created because a softphone must **register (REGISTER → 200 OK)**
> before it can place/receive a call and open a media peer connection. The failure happens *before*
> WebRTC media — so this is a **SIP signaling/authentication** problem, not a WebRTC/ICE/TURN problem.

---

## The smoking gun — the SIP exchange

The PBX challenges the phone (normal), the phone answers with a correctly-formed MD5 digest
(normal), and the PBX **rejects the answer** (the problem):

**1. Server challenge (`401`, fresh nonce — this is expected on first REGISTER):**
```
SIP/2.0 401 Unauthorized
To: <sip:28850-20026@1-8-phx.xensub.net>;tag=...
CSeq: 81 REGISTER
WWW-Authenticate: Digest realm="asterisk",
    nonce="1781809613/8cbb8f437400eca844ea892c8fe28bfa",
    opaque="1b8374bb1c17bd0d", algorithm=MD5, qop="auth"
Server: Asterisk PBX certified-20.7-cert4
```

**2. Phone's authenticated retry (well-formed — username known, digest computed, nonce/opaque echoed):**
```
REGISTER sip:1-8-phx.xensub.net SIP/2.0
CSeq: 82 REGISTER
Authorization: Digest algorithm=MD5, username="28850-20026", realm="asterisk",
    nonce="1781809613/8cbb8f437400eca844ea892c8fe28bfa",
    uri="sip:1-8-phx.xensub.net",
    response="084a5d3b28f7b743e6e4571a15ad49f1",
    opaque="1b8374bb1c17bd0d", qop=auth, cnonce="iqqgq7nj2emf", nc=00000001
User-Agent: xwsphone.0.7.2
```

**3. Server rejects the *authenticated* request again → `401` (with a new nonce), forever:**
```
SIP/2.0 401 Unauthorized
CSeq: 82 REGISTER
WWW-Authenticate: Digest realm="asterisk", nonce="...new..."
```
```
console: !!!! RegisterFailed  IncomingResponse Authentication Error
console: .ua.registrationFailed - timer executing; reseeding .register
```

This repeats: CSeq 81 → 82 → … → 102+, dozens of times, no `200 OK`.

**What `401`-after-credentials means precisely:** the `username` (`28850-20026`) is *recognized* by the
PBX — otherwise we'd see `403/404` or an unknown-user rejection. The digest **`response` hash is
computed from the SIP secret**; the PBX recomputes it with *its* stored secret and they don't match.
→ **The SIP password provisioned into this agent's phone ≠ the SIP password configured on the PBX
endpoint.** This is a credential/provisioning mismatch on ReadyMode's side, not a client fault.

It is **not** a stale-nonce/clock issue either: the server issues a **fresh nonce on every 401**, the
phone uses each exactly once (`nc=00000001`), and the new answer is still rejected.

---

## Why this is ReadyMode's side, not the client's (evidence)

A client/network/browser problem produces *different* symptoms than what we saw:

| If the cause were… | We would see… | We actually saw… |
|---|---|---|
| Firewall / proxy blocking the phone | WSS to `:5013`/`:8079` **fails to open** | both **open fine** |
| VPN / ISP blocking UDP / NAT issues | **STUN fails**, ICE never gathers | **STUN succeeds** repeatedly |
| Browser / WebRTC disabled / mic blocked | `getUserMedia` error / no media | mic faked-OK; never reached |
| CORS / HTTP / auth / server-down | 4xx/5xx responses, failed XHRs | **0** HTTP errors |
| Wrong ReadyMode login password | login fails, app never loads | login OK, **app channel fully works** |
| **PBX SIP secret mismatch** | **`401` loop on REGISTER, app channel up = "half connected"** | **exactly this** ✅ |

The app/event channel (`:8079`) being fully alive while SIP (`:5013`) returns `401` is the textbook
signature of "half connected": ReadyMode's web/app session authenticated correctly, but the *separate*
SIP/voice credential is wrong. The two use different credentials, and only the SIP one is broken.

The fact that it reproduces from a **completely different network** (the owner's connection) confirms
it travels with the **account/extension**, not the location.

---

## Root cause

> **The SIP endpoint secret for extension `28850-20026` on ReadyMode's Asterisk PBX
> (`certified-20.7-cert4`, host `1-8-phx.xensub.net`) is out of sync with the secret ReadyMode's web
> app injects into the agent's softphone at login.** Every SIP `REGISTER` therefore fails digest
> authentication (`401`), the voice channel never registers, and the phone is stuck at "Preparing
> connection / half connected" and never reaches "Connected."

This is consistent with the reported pattern — **several agents, ~1 week**: a server-side event
(PBX upgrade/migration — note the *certified* Asterisk build; a bulk credential/password rotation; or
a provisioning-sync bug) desynced the SIP secret for a **subset of extensions**. The affected agents
cannot fix it because the SIP secret is **not** their login password and is not user-editable.

---

## Recommended fixes (in priority order)

### 1. (Primary) Re-provision the SIP secret for the affected extensions — ReadyMode admin
For each affected agent, force ReadyMode to regenerate/re-push the phone's SIP credential so the
web-injected secret matches the PBX endpoint again. In practice this is usually one of:
- Open the agent's profile in ReadyMode admin → **re-save the Phone / WebRTC settings** (this typically
  re-provisions the Asterisk endpoint secret), then have the agent hard-reload and re-login.
- If available, use a **"reset/regenerate softphone password"** action on the extension.
- Resetting the agent's account password and re-saving sometimes triggers re-provisioning — try on one
  agent and re-test before doing it for all.

After the change, re-run this diagnostic (or just watch the phone): success looks like a single
`REGISTER → 401 (challenge) → REGISTER(auth) → 200 OK`, then status flips to **Connected**.

### 2. (If #1 doesn't stick) Escalate to ReadyMode support with this evidence
Because it hit multiple agents at once, the cleanest fix is on their PBX. Give them exactly:
- Tenant `resva7`, PBX `Asterisk certified-20.7-cert4`, host `1-8-phx.xensub.net`.
- Symptom: **`REGISTER` returns `401 Unauthorized` even after a valid digest response; never `200 OK`.**
  The endpoint username is accepted but the secret is rejected → **endpoint secret mismatch /
  provisioning desync** for a subset of extensions.
- The **list of affected extension IDs** (e.g. `28850-20026` for `RES-1245`; collect the rest).
- Ask directly: *"Did a PBX upgrade/migration or a bulk credential rotation happen ~1 week ago that
  could have left the Asterisk endpoint secrets out of sync with the provisioned softphone secrets?"*

### 3. (Verification / scoping — recommended next step)
Run the **same** harness from the **same** machine against a **known-good agent** (one whose phone
*does* connect). Expected: that agent gets `SIP/2.0 200 OK` and reaches "Connected." That A/B test
**proves** the issue is per-account (server-side), not environmental — useful leverage with ReadyMode.
*(I can do this immediately if you give me one working agent's credentials.)*

### What will NOT fix it (and why a week of IT effort didn't work)
These are all client-side and the data shows the client is healthy — skip them:
- Changing/reinstalling the browser, clearing cache, new profile
- Disabling VPN, changing networks, opening firewall ports
- New headset/microphone, Windows audio/privacy settings
- Reinstalling anything on the agent's PC

The phone reaches ReadyMode, opens both WebSockets, passes STUN, and the app channel works. The only
failure is the PBX rejecting the SIP password — which lives on ReadyMode's servers.

---

## Evidence artifacts
- `scratch/phone-diag/diag.js` — the instrumented diagnostic harness (re-runnable:
  `NODE_PATH="$(npm root -g)" node diag.js <subdomain> <user> <pass> [seconds]`)
- `scratch/phone-diag/capture.json` — full structured timeline (577 events incl. all SIP frames)

### Reproduce
```bash
cd scratch/phone-diag
NODE_PATH="$(npm root -g)" node diag.js resva7 'RES-1245' '<password>' 90
```
A connected agent will show `SIP/2.0 200 OK` after the authenticated REGISTER; this account never does.

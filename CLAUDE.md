# CLAUDE.md - VOS Project Standing Instructions

## SESSION START — Load Second Brain
At the start of every session, before anything else:
1. Read `C:\Users\vos\Desktop\obsidian_brain\index.md`
2. Read `C:\Users\vos\Desktop\obsidian_brain\01-projects\VOS Railway (QA Automation).md`
3. Read `C:\Users\vos\Desktop\obsidian_brain\03-decisions\Known Gotchas.md`

This is your memory. Use it to understand what was done before, what's in progress, and what gotchas to avoid.

---

> **This file contains permanent instructions for how to work on VOS with Claude.**  
> Updated: 2026-05-02 | Owner: Mohamed Ibrahim Abdo

---

## Git Remote — CRITICAL

This project has **two remotes**. Always push to `vos-tool`, never `origin`:

```
origin    → https://github.com/MOHAMEDVOS/vos-tool-2.0-version-.git  ← WRONG REPO
vos-tool  → https://github.com/MOHAMEDVOS/vos-tool.git               ← CORRECT REPO
```

**Always use:** `git push vos-tool <branch>`  
**Never use:** `git push origin <branch>`

Current working branch: `fix/railway-session-auth`

---

## What is VOS?

**Voice Observation System** — Your AI-powered call center QA automation tool.

Built to automatically analyze Egyptian real estate sales calls:
- 🎤 Transcribes audio (AssemblyAI)
- 🧠 Detects rebuttals (2000+ phrase library, 3-layer confidence system)
- 📊 Flags quality issues (late hello, releasing, agent-only)
- 📈 Tracks agent performance

**Why you built it:** Manual analysis took 45s per call. VOS does it in 2-3s and costs $2-3 per 1000 calls (vs $15-20 naive approach).

---

## Architecture at a Glance

```
Frontend (React 19)   ←→  Backend (FastAPI)  ←→  PostgreSQL
  webapp/ (Vite+TS)        port 8000             on Railway
  served via nginx              ↓
                        lib/ + backend/ (core logic)
                        - audio_pipeline/
                        - analyzer/ (3-layer detection)
                        - automation/ (pure HTTP)
                        - dashboard_manager.py
                        
External Services:
- AssemblyAI (transcription)
- Groq / Llama 3.3 70B (LLM fallback)
- Sentence Transformers (semantic matching)
- ReadyMode dialers (call downloads, pure HTTP)
- Google OAuth / Drive / Docs
```

**Deployment:** Railway via Docker — Backend (8000), Frontend (React/nginx), PostgreSQL. Redis + Celery are configured in the codebase for background jobs.

---

## Key Files to Know

| File | Purpose | Status |
|------|---------|--------|
| `webapp/` | React 19 + Vite + TS frontend (SPA, served via nginx) | Active UI |
| `backend/main.py` | FastAPI app — routers, CORS, lifespan | Critical |
| `lib/dashboard_manager.py` | Core data manager (~2000 lines) | Critical, god-class |
| `lib/analyzer/rebuttal_detection.py` | 3-layer detection logic | Brilliant optimization |
| `lib/phrase_learning.py` | Auto-learn new rebuttals | Working well |
| `automation/readymode_http.py` | ReadyMode pure-HTTP client (login, fetch, download) | Working well |
| `docs/ARCHITECTURE.md` | Architecture reference | Up-to-date |
| `docs/DETECTION_WORKFLOW.md` | 3-layer detection explained | Up-to-date |
| `docs/IMPROVEMENTS.md` | Suggestion list (no changes yet) | Reference only |

---

## How to Work on VOS

### 1. On Every Request: Use Skills First

**MANDATORY:** Before coding or significant analysis, use your brainstorming and planning skills.

```
When you get a request:
1. Read .agents/skills/brainstorming/SKILL.md
2. Apply brainstorming to explore options
3. Read .agents/skills/writing-plans/SKILL.md
4. Write a plan before implementing
5. Share plan/brainstorm output with the user
```

**Why:** You've built these skills into the project. They prevent tunnel vision and ensure alignment.

### 2. Analysis = Documentation

When you analyze code:
- ✅ Create .md files documenting your findings
- ✅ Create HTML visualizations if helpful
- ✅ Point to files instead of explaining in chat
- ❌ Don't just chat about it

When you improve code:
- ✅ Suggest improvements (list with impact analysis)
- ✅ Implement only on explicit request ("fix this", "add this feature")
- ❌ Don't implement unasked improvements
- ❌ Don't refactor surrounding code that wasn't requested

### 3. Respect the Domain

VOS is **Egyptian real estate sales QA automation.**

- The 2000+ phrase library is domain-specific (objections to property deals)
- The 80+ Egyptian accent correction patterns matter
- The 8 rebuttal strategies in LLM evaluation are sales-specific
- Cost and speed optimizations are core to the value prop

When suggesting changes, consider domain impact.

### 4. Understand the Constraints

**Railway deployment has limits:**
- Connection pool size: Currently 200 (should reduce to 30-50)
- Celery workers: Must match CPU count
- Memory: ~1GB per service
- Database: Shared PostgreSQL, not unlimited

**Performance is a feature:**
- 80% early-exit rate (Layer 1/2 resolution)
- 2.5 hours per 1000 calls (vs 12.5 without optimization)
- $2-3 cost per 1000 calls (vs $15-20 naive)

Don't suggest changes that break these metrics.

### 5. Critical Infrastructure

**Don't touch without explicit approval:**
- `webapp/` auth/routing shell + `backend/api/auth.py` (Google OAuth + JWT flow)
- `lib/dashboard_manager.py` user/audit/quota logic
- Database schema (unless migrating with Alembic)
- Password hashing (currently using two systems — needs consolidation)

**Safe to improve:**
- Add rate limiting (slowapi present, toggled)
- Migrate to bcrypt (with migration strategy)
- Add tests for core paths
- Optimize connection pool

---

## Quality Expectations

### Code You Write for VOS

- ✅ Follow existing patterns (lib/ module structure, FastAPI routes, React components/pages in webapp/)
- ✅ Include error handling at system boundaries (user input, external APIs)
- ✅ Log important decisions (not silent catches)
- ✅ Test before submitting (run test suite if exists)
- ❌ Don't add speculative features
- ❌ Don't refactor code you didn't change
- ❌ Don't add comments unless logic is non-obvious

### When Documenting

- ✅ ARCHITECTURE.md is the reference — keep it current
- ✅ Code comments should explain "why", not "what"
- ✅ Use tables, diagrams, examples for clarity
- ✅ Include metrics (time, cost, accuracy) for optimizations
- ❌ Don't over-document; say exactly what's needed

---

## Current Known Issues (IMPORTANT)

From `docs/IMPROVEMENTS.md` — prioritized by security/impact:

### CRITICAL (Fix Soon)
1. **SHA256 password hashing** (no salt) → Migrate to bcrypt
2. **JWT secret fallback values** → Fail fast in production
3. **verify_password not constant-time** → Use hmac.compare_digest

### HIGH (Important But Lower Priority)
4. **sys.path.insert() in 18+ files** → Add proper pyproject.toml
5. **Two password hashing systems** → Unify on lib/security_utils.py
6. **No database migration system** → Add Alembic

### MEDIUM (Quality of Life)
8. **Connection pool 200 on Railway** → Reduce to 30-50
9. **dashboard_manager.py god-class** → Split into session/user/audit/quota managers
10. **Rate limiting disabled** → Re-enable slowapi or Redis-based

---

## Memory Files Available

All stored in `C:\Users\vos\.claude\projects\c--Users-vos-Desktop-VOS-railway\memory\`:

- **user_role.md** — You're the owner/developer, prefer skills & files
- **project_vos_core.md** — Complete project overview, tech stack, workflows
- **feedback_development_preferences.md** — How you like Claude to work
- **MEMORY.md** — Index of all memory files

**These persist across sessions.** Claude will have full context on VOS in future conversations.

---

## Success Metrics

✅ **You'll know Claude is helping well when:**
- Documentation is accurate and up-to-date (ARCHITECTURE.md, DETECTION_WORKFLOW.md)
- Improvements come with impact analysis (time, cost, security)
- Code changes only happen after explicit approval
- Skills are used for planning significant work
- Responses are concise and point to files
- Domain context (Egyptian real estate) is understood

❌ **Red flags:**
- Code changes you didn't ask for
- Long chat explanations (use .md instead)
- Skills not used
- Improvements implemented without approval

---

## Your Next Step

When you need Claude's help on VOS:
1. Describe what you need
2. Claude will use brainstorming/planning skills
3. Claude will create documentation
4. Claude will suggest or implement (based on your request)

**You stay in control. Claude helps you understand and improve VOS, but respects that it's YOUR project.**

---

**Useful Links:**
- `docs/ARCHITECTURE.md` — Full architecture reference
- `docs/DETECTION_WORKFLOW.md` — 3-layer detection explained  
- `docs/IMPROVEMENTS.md` — Suggestions for improvements
- `docs/VOS_WORKFLOW.html` — Interactive visual workflow

---

## Knowledge Base (Obsidian)

**Vault:** `C:\Users\vos\Desktop\obsidian_brain`
**Project doc:** `01-projects/VOS Railway (QA Automation).md`

When significant changes happen, update the vault:
- Known issue fixed → move it out of the Known Issues list in project doc
- New feature shipped → add to project doc
- Bug or gotcha discovered → add to `03-decisions/Known Gotchas.md`
- Performance metrics change → update the Performance Metrics table
- New runbook needed → create in `04-how-to/`
- Session log → append to the **Session Log** section in the project doc

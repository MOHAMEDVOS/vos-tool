---
name: senior-fullstack
description: "Approach fullstack development (Python backend + HTML/JS frontend) with senior engineering practices: clean architecture, separation of concerns, error handling, and maintainability."
---

# Senior Fullstack Development Skill

## Overview
This skill guides you to write production-quality fullstack code across Python backends and web frontends — with proper error handling, clean architecture, and long-term maintainability in mind.

## When to Use
- When building new features that span backend and frontend
- When reviewing or improving existing code quality
- When something is getting messy or hard to maintain
- When adding API endpoints or modifying Flask routes

## Core Principles

### 1. Separation of Concerns
- **Backend** handles: data, business logic, authentication, file I/O
- **Frontend** handles: display, user interaction, form state
- Never mix them: don't put business logic in templates, don't put SQL in routes

```python
# BAD: logic in route
@app.route("/agent/<id>")
def agent(id):
    agent = db.execute("SELECT * FROM agents WHERE id=?", id)
    if agent["ping"] > 100:
        agent["status"] = "slow"
    return jsonify(agent)

# GOOD: logic in a service/model
@app.route("/agent/<id>")
def agent(id):
    agent = AgentService.get_with_status(id)  # logic lives here
    return jsonify(agent)
```

### 2. Error Handling — Always
Every function that can fail MUST handle that failure:
```python
# BAD
def get_agent(id):
    return db.query(f"SELECT * FROM agents WHERE id={id}")

# GOOD
def get_agent(agent_id: str) -> dict | None:
    try:
        result = db.execute("SELECT * FROM agents WHERE id=?", (agent_id,))
        return result.fetchone()
    except Exception as e:
        logger.error(f"Failed to fetch agent {agent_id}: {e}")
        return None
```

### 3. API Design
- Use consistent response shapes: `{"success": bool, "data": ..., "error": str|null}`
- Use proper HTTP status codes: 200, 400, 404, 500
- Validate all inputs before processing

### 4. Frontend Best Practices
- Use `fetch()` with proper error handling — always check `response.ok`
- Never trust data from the server — validate before rendering
- Use loading states so the user knows something is happening

```javascript
async function fetchAgents() {
    try {
        const res = await fetch('/api/agents');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderAgents(data.agents);
    } catch (err) {
        showError('Failed to load agents: ' + err.message);
    }
}
```

### 5. Logging
Log at the right level:
- `DEBUG`: detailed flow info (dev only)
- `INFO`: normal operations ("Agent 001 checked in")
- `WARNING`: unexpected but recoverable ("No ping data, using cached")
- `ERROR`: failures that need attention ("Database write failed")

### 6. Configuration
- Never hardcode URLs, ports, or credentials
- Use `config.json` or environment variables
- Example: `app.config.from_file("config.json", load=json.load)`

## This Project's Stack
- **Backend**: Python 3, Flask, SQLite (`team_results.db`)
- **Frontend (dashboard)**: Jinja2 templates + Vanilla JS
- **Frontend (app)**: Vite + React + TypeScript + Tailwind
- **Testing**: pytest + Playwright
- **Build**: PyInstaller (`VOS.spec`) + Vite

## Code Quality Checklist
```
[ ] Functions have clear names that describe what they do
[ ] No function is longer than 50 lines
[ ] All error cases are handled
[ ] No hardcoded values (use constants or config)
[ ] Logging added at key decision points
[ ] Input validation before processing
[ ] Tests written for new logic
```

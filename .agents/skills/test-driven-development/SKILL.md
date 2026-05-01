---
name: test-driven-development
description: "Write tests before implementation. Red → Green → Refactor. Never write code without a failing test first."
---

# Test-Driven Development (TDD) Skill

## Overview
TDD is a development practice where you write a failing test FIRST, then write the minimum code to make it pass, then refactor. This prevents bugs at the source and ensures every feature is testable.

## When to Use
- When adding any new feature or function
- When fixing a bug (write a test that exposes the bug first)
- When refactoring (ensure tests pass before and after)

## The TDD Cycle: Red → Green → Refactor

### 🔴 Red: Write a Failing Test
Write a test for the behavior you WANT — before writing the code.
```python
def test_pdf_shows_approved_status():
    report = generate_pdf(agent_id="001", approved=True)
    assert "APPROVED" in report.text
    assert "does not meet requirements" not in report.text
```
Run the test — it MUST fail. If it passes, you wrote the wrong test.

### 🟢 Green: Write Minimum Code to Pass
Write the simplest code that makes the test pass. Don't over-engineer.
```python
def generate_pdf(agent_id, approved):
    status = "APPROVED" if approved else "NOT APPROVED"
    return render_template("report.html", status=status)
```
Run the test — it MUST now pass.

### 🔵 Refactor: Clean Up
Improve the code without changing behavior. Tests must still pass after refactoring.

## Rules
1. **Never write code without a failing test first**
2. **Write only enough code to make the test pass**
3. **Each test should test ONE thing**
4. **Tests must be fast** (< 1 second each ideally)
5. **Tests must be independent** (order shouldn't matter)

## For This Project (Python / Flask / Playwright)

### Unit tests (pytest):
```python
# tests/test_pdf.py
def test_generate_pdf_approved():
    ...

def test_generate_pdf_rejected_includes_reason():
    ...
```

### Integration tests (Flask test client):
```python
def test_dashboard_api_returns_agents(client):
    response = client.get("/api/agents")
    assert response.status_code == 200
    assert "agents" in response.json
```

### UI tests (Playwright):
```python
def test_dashboard_shows_agent_count(page):
    page.goto("http://localhost:5000")
    assert page.get_by_text("Total Agents").is_visible()
```

## Running Tests
```powershell
# Run all tests
pytest VOS/tests/ -v

# Run specific file
pytest VOS/tests/test_pdf.py -v

# Run with coverage
pytest --cov=VOS VOS/tests/
```

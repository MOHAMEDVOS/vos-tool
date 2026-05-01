---
name: webapp-testing
description: "Test web applications thoroughly using Playwright. Write reliable selectors, handle async, and test real user flows."
---

# Web App Testing Skill (Playwright)

## Overview
This skill guides structured, reliable testing of web applications using Playwright. It covers writing maintainable tests, selecting elements correctly, handling async operations, and verifying real user flows.

## When to Use
- When writing Playwright tests for the dashboard or any web UI
- When a bot or scraper is failing to find elements
- When tests are flaky or intermittently failing
- When adding a new feature that affects the UI

## Instructions

### Step 1: Understand the User Flow
- Before writing any test, write out the user flow in plain English
- Example: "User opens dashboard → filters by 'Issues' tab → clicks an agent → views their PC spec"

### Step 2: Write Reliable Selectors
- Prefer `data-testid` attributes over CSS classes or text
- Use `page.getByRole()`, `page.getByLabel()`, `page.getByText()` — not fragile CSS paths
- Avoid selecting by auto-generated class names (e.g., `.css-abc123`)
- Add `data-testid` attributes to the HTML source if needed

### Step 3: Handle Async Properly
- Always `await` Playwright actions — never fire-and-forget
- Use `page.waitForSelector()` or `page.waitForLoadState()` for dynamic content
- Never use `time.sleep()` or `asyncio.sleep()` to wait — use proper Playwright waits

### Step 4: Structure Your Tests
```python
import pytest
from playwright.sync_api import Page, expect

def test_dashboard_loads(page: Page):
    page.goto("http://localhost:5000")
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()

def test_filter_by_issues(page: Page):
    page.goto("http://localhost:5000")
    page.get_by_role("tab", name="Issues").click()
    expect(page.get_by_text("No issues found")).to_be_visible()
```

### Step 5: Test Error States
- Test what happens when the server is down
- Test what happens with no data / empty tables
- Test form validation errors

### Step 6: Run and Fix Flaky Tests
- If a test fails intermittently, add `expect(element).to_be_visible()` before interacting
- Use `page.wait_for_load_state("networkidle")` for pages that load data via API

### Step 7: CI Integration
- Ensure tests can run headless: `--headless` flag in Playwright
- Export test results with `--output=results/` for CI artifacts

## Selector Priority (Best → Worst)
1. `data-testid` attributes ← **Best**
2. ARIA roles (`getByRole`)
3. Labels (`getByLabel`)
4. Text content (`getByText`)
5. CSS selectors ← **Avoid**
6. XPath ← **Never use**

## Common Issues in This Project
- Chat selector flakiness: use `page.wait_for_selector(".chat-bubble", state="visible")`
- Unread badge: use `page.get_by_role("status")` or a `data-testid="unread-count"`
- Dashboard table: wait for `networkidle` before asserting row counts

---
name: writing-plans
description: "Write detailed, actionable implementation plans before coding. Think before you build."
---

# Writing Plans Skill

## Overview
Before writing any significant code, write a clear implementation plan. This prevents wasted effort, catches design flaws early, and ensures the work aligns with the actual goal.

## When to Use
- Before implementing any feature that touches more than 2 files
- Before any refactoring effort
- When a task feels complex or multi-step
- When you're unsure of the approach — plan it out first

## Plan Structure

### 1. Problem Statement (2-3 sentences)
What is the actual problem? Why does it need solving?
> "The PDF report incorrectly displays 'does not meet requirements' even when the agent's PC spec has been manually approved. This causes confusion and erodes trust in the system."

### 2. Root Cause (if debugging)
What is causing the problem?
> "The `generate_pdf()` function passes `spec.approved` to the template, but the field is stored as `spec.is_approved`. The template receives `None` and treats it as `False`."

### 3. Proposed Solution
One paragraph on the approach:
> "Fix the field name passed to the template. Add defensive logging before PDF generation to catch future field mismatches. Add a regression test."

### 4. Files to Change
List every file and what changes:
| File | Change |
|------|--------|
| `dashboard_server.py` | Fix field name in `generate_pdf()` call |
| `templates/report.html` | Add fallback display for missing approval reason |
| `tests/test_pdf.py` | Add test for approved and rejected states |

### 5. Testing Plan
How will you verify this is fixed?
1. Generate a PDF for an agent with `is_approved=True` → verify "APPROVED" appears
2. Generate a PDF for an agent with `is_approved=False` and a reason → verify reason appears
3. Run regression: existing tests still pass

### 6. Risks & Rollback
What could go wrong? How to undo if needed?
> "Low risk — field name fix. Rollback: revert the one-line change in `dashboard_server.py`."

## Example Plan (Markdown)
```markdown
# Plan: Fix PDF Approval Status Bug

## Problem
PDF shows "not approved" even when agent is approved.

## Root Cause
`generate_pdf()` uses `spec.approved` but field is `spec.is_approved`.

## Solution
Fix field name. Add logging. Add test.

## Files
- `dashboard_server.py` line 342: change `spec.approved` to `spec.is_approved`
- `tests/test_pdf.py`: add two new test cases

## Test Plan
1. Approved agent → PDF shows "APPROVED"
2. Rejected agent → PDF shows reason

## Risks
None significant. One-line fix.
```

## Rules
- Plans should take 5-10 minutes to write — not half a day
- A plan is NOT a full specification — just enough clarity to code confidently
- If the plan reveals uncertainty, **do research first** before continuing
- Update the plan if the implementation reveals new information

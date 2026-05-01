---
name: systematic-debugging
description: "Debug code systematically and methodically, not randomly. Identify root causes, not just symptoms."
---

# Systematic Debugging Skill

## Overview
This skill guides you to debug issues in a structured, methodical way — identifying the actual root cause rather than chasing symptoms or applying random fixes.

## When to Use
- When a bug is reported and the cause is unclear
- When a fix was applied but the bug keeps reappearing
- When something "worked before" but now doesn't
- Before applying any patch or workaround

## Instructions

### Step 1: Reproduce the Bug
- Find the exact steps to reproduce the issue reliably
- If you can't reproduce it, you can't debug it
- Note: exact inputs, environment, and expected vs actual behavior

### Step 2: Understand the System
- Read the relevant code paths before guessing
- Trace the data flow from input to the point of failure
- Check recent changes (git log/diff) that could have caused this

### Step 3: Form a Hypothesis
- State clearly: "I think the bug is caused by X because Y"
- Only one hypothesis at a time — test before moving on
- Don't fix multiple things at once "just to try"

### Step 4: Test the Hypothesis
- Add targeted logging or print statements at the suspected location
- Use assertions to verify your assumptions
- Run the reproduction steps with the hypothesis in mind

### Step 5: Fix the Root Cause
- Fix the actual root cause, not the symptom
- If fixing X requires changing 10 things, reconsider your hypothesis
- A good fix is usually small and targeted

### Step 6: Verify the Fix
- Run the exact reproduction steps again
- Ensure no regressions were introduced
- Remove any debug logging added in step 4

### Step 7: Document
- Write a brief comment in code explaining WHY the fix was needed
- Update tests to prevent regression

## Common Anti-patterns to Avoid
- DO NOT apply multiple fixes at once — you won't know what worked
- DO NOT guess and check blindly — form a hypothesis first
- DO NOT skip reproduction — if you can't reproduce it, you can't confirm the fix
- DO NOT fix the symptom — find and fix the root cause

## Examples

### Bad approach:
```
Bug: PDF shows wrong approval status
Fix attempt 1: Change the condition
Fix attempt 2: Change the variable name
Fix attempt 3: Reload the page
```

### Good approach:
```
Bug: PDF shows wrong approval status
Reproduce: Generate PDF for agent with approved=True, see "not approved"
Hypothesis: The PDF template reads `spec.approved` but the field is `spec.is_approved`
Test: Add logging to print both values before PDF generation
Confirm: Correct the field name → re-verify → bug gone
```

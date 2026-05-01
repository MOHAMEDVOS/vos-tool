---
name: verification-before-completion
description: "Always verify your work is actually correct and complete before claiming it is done. Never say 'done' without proof."
---

# Verification Before Completion Skill

## Overview
Before marking any task as complete, run through a structured verification checklist to confirm the work actually functions as intended. This prevents shipping broken code or incomplete features.

## When to Use
- Before telling the user "it's done" or "fixed"
- After implementing any feature or bug fix
- Before committing or merging code
- After making changes that affect multiple parts of the codebase

## Instructions

### Step 1: Re-read the Original Requirement
- Restate in your own words what was asked for
- Confirm your implementation matches what was requested — not just what you built

### Step 2: Trace Through the Implementation
- Walk through the code path manually from start to finish
- Check: does data flow in → transform correctly → come out correctly?
- Check all edge cases: empty input, null values, unexpected types

### Step 3: Run the Code
- Don't just read the code — actually run it
- Run with the exact inputs from the original bug report or requirement
- Verify the output matches expected behavior

### Step 4: Check for Side Effects
- Did your change break anything else?
- Run the full test suite if available
- Check related functionality that may be affected

### Step 5: Review Your Own Diff
- Read every line you changed
- Ask: "Is this the minimal change needed?"
- Look for introduced bugs, typos, or missing cases

### Step 6: Confirm with Evidence
- Capture a log output, screenshot, or test result as proof
- Only then state the task is complete

## Checklist Template
```
[ ] Requirement re-read and understood
[ ] Code path traced manually  
[ ] Code actually executed with test input
[ ] Output matches expected result
[ ] No regressions in related features
[ ] Diff reviewed line-by-line
[ ] Evidence of working captured
```

## Anti-patterns to Avoid
- DO NOT say "should work now" without running it
- DO NOT mark a ticket done based on code inspection alone
- DO NOT skip edge cases (empty data, network failure, missing fields)
- DO NOT forget to check that existing functionality still works

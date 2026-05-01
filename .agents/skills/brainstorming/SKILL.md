---
name: brainstorming
description: "Explore ideas and design solutions before starting to code. Generate multiple options and choose the best one."
---

# Brainstorming Skill

## Overview
Before diving into implementation, use structured brainstorming to explore the problem space, generate multiple approaches, and consciously choose the best one. This prevents tunnel vision and leads to better solutions.

## When to Use
- When starting a new feature and unsure of the best approach
- When a current approach isn't working and you need fresh ideas
- When trade-offs need to be made (performance vs simplicity, etc.)
- When the user describes a problem but the solution isn't obvious

## Brainstorming Process

### Step 1: Restate the Problem
Write the problem in your own words. Be precise.
> ❌ "Make the dashboard better"
> ✅ "Users need to quickly identify agents with connectivity issues without scrolling through all 200+ agents"

### Step 2: Generate Options (at least 3)
Don't evaluate yet — just generate. Quantity over quality at this stage.

**For the example:**
- Option A: Add a filter tab for "Issues"
- Option B: Sort the table by status, issues first
- Option C: Add a red badge count on the top navigation
- Option D: Send an email/notification alert for new issues
- Option E: Add a search/filter input box

### Step 3: Evaluate Each Option
For each option, consider:
| | Effort | Impact | Risk | User Clarity |
|--|--------|--------|------|--------------|
| A: Filter tab | Low | High | Low | High |
| B: Auto-sort | Low | Medium | Low | Medium |
| C: Badge count | Medium | Medium | Low | High |
| D: Email alerts | High | High | Medium | High |
| E: Search box | Medium | Medium | Low | High |

### Step 4: Choose and Justify
Pick the best option and state why.
> "Choosing **A + C** (filter tab + badge count). Filter tab gives instant access, badge count gives at-a-glance awareness. Both are low effort, high impact, and easy for users to understand."

### Step 5: Define Success
How will you know it worked?
> "Success: A user can click 'Issues' tab and see all problem agents within 2 seconds. Badge count updates in real-time."

## For This Project — Brainstorming Templates

### Feature Brainstorm
```
Problem: [specific user pain point]
Current behavior: [what happens now]
Desired behavior: [what should happen]

Options:
1. [Name]: [brief description] — Effort: [L/M/H], Impact: [L/M/H]
2. [Name]: [brief description] — Effort: [L/M/H], Impact: [L/M/H]
3. [Name]: [brief description] — Effort: [L/M/H], Impact: [L/M/H]

Chosen: Option [X] because [reason]
Success metric: [how to know it worked]
```

### Bug Fix Brainstorm
```
Bug: [what's broken]
Hypotheses about cause:
1. [Hypothesis A] — Likelihood: [H/M/L]
2. [Hypothesis B] — Likelihood: [H/M/L]
3. [Hypothesis C] — Likelihood: [H/M/L]

Best hypothesis to test first: [X] because [reasoning]
How to test: [specific steps]
```

## Rules
- Never skip to code before brainstorming for medium+ complexity tasks
- Generate at least 3 options — the first idea is rarely the best
- Explicitly state WHY you're choosing your option
- Time-box brainstorming: 5-15 minutes max for most tasks

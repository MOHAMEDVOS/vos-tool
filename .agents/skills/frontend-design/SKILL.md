---
name: frontend-design
description: "Build production-grade frontend interfaces with clean HTML, CSS, and JavaScript. Focus on usability, visual hierarchy, and maintainability."
---

# Frontend Design Skill

## Overview
This skill guides building clean, professional frontend interfaces using HTML, CSS, and JavaScript — with a focus on usability, responsive design, and visual quality.

## When to Use
- When building or improving dashboard HTML templates
- When a UI looks unprofessional or cluttered
- When adding new UI sections to the app
- When improving the user experience of a form or table

## Design Principles

### 1. Visual Hierarchy
- The most important info should be the biggest and most prominent
- Use headings (h1 → h2 → h3) correctly — don't skip levels
- Use whitespace intentionally — crowded ≠ professional

### 2. Color System
Use a consistent color palette — don't pick colors ad hoc:
```css
:root {
    --color-primary: #2563EB;       /* Brand blue */
    --color-success: #16A34A;       /* Green for OK */
    --color-warning: #D97706;       /* Amber for caution */
    --color-danger: #DC2626;        /* Red for errors */
    --color-surface: #1E293B;       /* Dark card background */
    --color-text: #F1F5F9;          /* Light text on dark */
    --color-muted: #94A3B8;         /* Secondary text */
}
```

### 3. Typography
- Use Google Fonts: Inter, Outfit, or Roboto for a premium feel
- Match font weights to importance: 700 for headings, 400 for body, 300 for captions
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
```

### 4. Component Patterns

**Status Badge:**
```html
<span class="badge badge--success">Online</span>
<span class="badge badge--danger">Offline</span>
```
```css
.badge { padding: 2px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.badge--success { background: #dcfce7; color: #166534; }
.badge--danger { background: #fee2e2; color: #991b1b; }
```

**Card:**
```css
.card {
    background: var(--color-surface);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
```

### 5. Responsive Design
- Use CSS Grid or Flexbox — never use float for layout
- Use `clamp()` for fluid font sizing
- Test at 768px (tablet) and 375px (mobile) widths

### 6. Micro-animations
Add subtle transitions to feel premium:
```css
.btn {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
```

### 7. Table Design (for dashboard)
```css
.table { width: 100%; border-collapse: collapse; }
.table th { 
    position: sticky; top: 0; 
    background: #1e293b; 
    padding: 12px 16px; 
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
}
.table tr:hover { background: rgba(255,255,255,0.03); }
.table td { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.06); }
```

## Dashboard-Specific Patterns (This Project)
- Keep the sidebar fixed, content area scrollable
- Use tab filters with pill style (not underline style)
- Sticky table headers for long agent lists
- Bulk action bar appears at bottom when rows are selected

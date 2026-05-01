---
name: ui-ux-pro-max
description: "Professional UI/UX design system. Color theory, typography, layout, spacing, and interaction design at a senior level."
---

# UI/UX Pro Max Skill

## Overview
This skill elevates UI/UX design to a professional standard — applying color theory, typography hierarchy, layout systems, and interaction design patterns used in modern SaaS products.

## When to Use
- When the UI looks "dated" or "amateur"
- When a redesign or visual refresh is needed  
- When designing a new section or page from scratch
- When the user wants the app to feel premium

## Design System Approach

### Step 1: Define the Design Token System
Before designing anything, define tokens:
```css
/* Spacing (8px base grid) */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--space-12: 48px;

/* Border radius */
--radius-sm: 6px;
--radius-md: 10px;
--radius-lg: 16px;
--radius-full: 999px;

/* Shadows */
--shadow-sm: 0 1px 3px rgba(0,0,0,0.12);
--shadow-md: 0 4px 12px rgba(0,0,0,0.15);
--shadow-lg: 0 8px 30px rgba(0,0,0,0.2);
```

### Step 2: Color Theory Fundamentals
- **Primary**: Your main brand action color (buttons, links, highlights)
- **Semantic**: Green/amber/red for status (never use for decoration)
- **Neutral**: Grays for backgrounds, borders, text at different opacities
- **Surface hierarchy**: Dark mode = darkest at back, lighter going forward

```css
/* Dark mode surface hierarchy */
--surface-base: #0F172A;      /* Page background */
--surface-raised: #1E293B;    /* Cards */
--surface-overlay: #273449;   /* Modals, dropdowns */
--surface-top: #334155;       /* Input backgrounds */
```

### Step 3: Typography Scale
```css
--text-xs: 0.75rem;    /* 12px - captions, labels */
--text-sm: 0.875rem;   /* 14px - secondary body */
--text-base: 1rem;     /* 16px - primary body */
--text-lg: 1.125rem;   /* 18px - lead text */
--text-xl: 1.25rem;    /* 20px - small headings */
--text-2xl: 1.5rem;    /* 24px - section headings */
--text-3xl: 1.875rem;  /* 30px - page headings */
```

### Step 4: Layout & Grid
- Use CSS Grid for page layout, Flexbox for component layout
- 12-column grid for large screens, 4-column for mobile
- Consistent sidebar: 260px fixed, content: fluid

### Step 5: Component Library (This Project)

**Stat Card:**
```html
<div class="stat-card">
    <div class="stat-icon">🟢</div>
    <div class="stat-value">247</div>
    <div class="stat-label">Agents Online</div>
    <div class="stat-delta stat-delta--up">+12 this week</div>
</div>
```

**Status Pill for Agent Table:**
```css
.status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: var(--radius-full);
    font-size: var(--text-xs); font-weight: 600;
}
.status-pill::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-pill.online { background: #dcfce722; color: #4ade80; }
.status-pill.offline { background: #fee2e222; color: #f87171; }
.status-pill.issues { background: #fef3c722; color: #fbbf24; }
```

### Step 6: Interaction Design
- Click areas ≥ 44×44px (touch targets)
- Hover states on all interactive elements
- Loading spinners for async operations
- Toasts/notifications disappear after 4 seconds
- Modals have a backdrop blur overlay

### Step 7: Motion Design
```css
/* Standard transition */
transition: all 0.2s ease;

/* Entrance animation */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
.card { animation: fadeInUp 0.3s ease; }
```

## Quality Checklist
```
[ ] Design tokens defined (no magic numbers)
[ ] Color contrasts pass WCAG AA (4.5:1 for text)
[ ] Type scale consistent (no random font sizes)
[ ] 8px grid followed throughout
[ ] All interactive elements have hover/focus states
[ ] Loading, empty, and error states designed
[ ] Responsive on narrow screens (768px min)
[ ] Motion is subtle (< 400ms, ease curves)
```

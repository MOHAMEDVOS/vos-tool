---
name: react-best-practices
description: "Write modern, maintainable React with TypeScript. Use hooks, avoid anti-patterns, and structure components properly."
---

# React Best Practices Skill

## Overview
This skill ensures your React/TypeScript frontend follows modern best practices — making it easier to maintain, debug, and extend.

## When to Use
- When building or modifying the Vite/React frontend (`src/` folder)
- When adding new UI components
- When a component is getting too large or complex
- When state management is getting messy

## Core Rules

### 1. Component Structure
```tsx
// One component per file
// Named exports (not default when possible)
export function AgentCard({ agent }: { agent: Agent }) {
    return (
        <div className="agent-card">
            <h3>{agent.name}</h3>
            <StatusBadge status={agent.status} />
        </div>
    );
}
```

### 2. TypeScript — Always Type Your Data
```tsx
// Define types for your data shapes
interface Agent {
    id: string;
    name: string;
    status: 'online' | 'offline' | 'issues';
    lastSeen: string;
}

// Never use `any`
function processAgent(agent: Agent): string {  // ✅
function processAgent(agent: any): string {    // ❌
```

### 3. Hooks Best Practices
```tsx
// ✅ Fetch data with useEffect + cleanup
useEffect(() => {
    let cancelled = false;
    fetch('/api/agents')
        .then(r => r.json())
        .then(data => { if (!cancelled) setAgents(data.agents); });
    return () => { cancelled = true; };
}, []);

// ✅ useCallback for handlers passed to children
const handleDelete = useCallback((id: string) => {
    setAgents(prev => prev.filter(a => a.id !== id));
}, []);
```

### 4. State Management
- Keep state as LOCAL as possible — lift up only when needed
- Use `useState` for simple local state
- Use `useReducer` when state logic is complex
- Use React Context sparingly (only for truly global state like user/theme)

### 5. Avoid Re-render Anti-patterns
```tsx
// BAD: new object created every render → child always re-renders
<Child style={{ color: 'red' }} />

// GOOD: stable reference
const redStyle = { color: 'red' };
<Child style={redStyle} />
```

### 6. Error Boundaries
Wrap key sections in error boundaries to prevent full-page crashes:
```tsx
<ErrorBoundary fallback={<div>Dashboard failed to load</div>}>
    <Dashboard />
</ErrorBoundary>
```

### 7. Loading & Error States
Always handle all three states:
```tsx
if (loading) return <Spinner />;
if (error) return <ErrorMessage error={error} />;
return <AgentList agents={agents} />;
```

## File Structure (for this project)
```
src/
  components/       # Reusable UI components
  pages/            # Page-level components
  hooks/            # Custom hooks (useFetch, useAgents, etc.)
  types/            # TypeScript interfaces
  utils/            # Pure utility functions
  App.tsx
  main.tsx
```

## Tailwind in this Project
- This project uses Tailwind CSS (`tailwind.config.js`)
- Use utility classes, don't write custom CSS unless absolutely needed
- Use `tailwind.config.js` to add custom colors/spacing for the brand

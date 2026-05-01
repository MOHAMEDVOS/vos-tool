# Remotion Development Guide

> Source: https://github.com/remotion-dev/remotion/blob/main/AGENTS.md

## Core Setup

Package manager: **Bun** (v1.3.3 required exactly)

```bash
bun install                    # install dependencies
bunx turbo run make            # build all packages
bunx turbo run lint test       # quality checks
```

## Before Submitting Work

1. `bun run build` — verify all packages compile
2. `bun run stylecheck` — required to pass CI
3. Include `bun.lock` when modifying dependencies

## PR Title Convention

```
`@remotion/package-name`: Description of change
```

Example: `` `@remotion/player`: Add loop prop ``

## Version Bumps

Increment patch number in `packages/core/src/version.ts`

## Development Testbeds

| Testbed | URL | Purpose |
|---------|-----|---------|
| Remotion Studio | http://localhost:3000 | Composition previews |
| Player testbed | — | Player-specific changes |
| Docs site | — | Docusaurus docs |

## Important Notes

- Packages interdepend on compiled artifacts — always build before testing
- Some packages need optional API keys (e.g. OpenAI) for full test coverage
- Go version dependency exists for some packages

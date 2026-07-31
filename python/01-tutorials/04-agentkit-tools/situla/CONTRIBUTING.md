# Contributing to Situla

Thank you for helping improve Situla.

## Development setup

Use Node.js 22.6 or newer for development. The official single-executable
release build is pinned to the version in `.node-version`.

```bash
npm install
npm run dev:server
```

In another terminal, start the Vite development server:

```bash
npm run dev
```

## Before submitting

Run the complete local verification:

```bash
npm run typecheck
npm test
npm run build
git diff --check
```

Tests use `node:test` and `node:assert/strict`. Add behavior-oriented regression
coverage for changed protocol payloads, redaction, Origin or capability checks,
retries, and state transitions.

Follow the existing strict TypeScript ESM style: two-space indentation, double
quotes, semicolons, explicit `.ts` imports, and trailing commas in multiline
declarations.

## Pull requests

Use a concise Conventional Commit subject. Explain user-visible behavior,
affected Admin or end-user surfaces, and verification commands. Include
screenshots for UI changes and call out protocol, authentication, or
configuration changes explicitly.

Do not commit OAuth codes, STS tokens, Endpoint query strings, local config
caches, or release credentials. Security vulnerabilities should be reported
privately as described in `SECURITY.md`.

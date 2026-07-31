# Repository Guidelines

## Project Structure & Module Organization

Situla is a TypeScript workspace for AgentKit sandboxes. Node-side control-plane, bridge, CLI, and proxy code lives in `src/`. The React/Vite UI lives in `web/src/`; route apps are `AdminApp.tsx` and `CodexApp.tsx`, with reusable UI under `web/src/components/` and hooks under `web/src/hooks/`. Tests are flat `test/*.test.ts` files named after their modules. Build tooling is in `scripts/`; binary inputs and release artifacts are under `.binary/` and `dist/`.

## Build, Test, and Development Commands

Use Node.js 22.6 or newer.

- `npm install` installs dependencies from `package-lock.json`.
- `npm run dev:server` starts the bridge in watch mode on `127.0.0.1:8787`.
- `npm run dev` starts Vite HMR on `127.0.0.1:5173`; run it beside the bridge.
- `npm run preview` builds the web UI and starts the integrated local application.
- `npm run typecheck` checks both Node and web TypeScript projects.
- `npm test` runs all `node:test` suites.
- `npm run build` creates the production Vite bundle; `npm run build:binary` creates the platform-specific SEA binary.

Before submitting, run `npm run typecheck`, `npm test`, `npm run build`, and `git diff --check`.

## Coding Style & Naming Conventions

Follow the strict TypeScript ESM style: two-space indentation, double quotes, semicolons, explicit `.ts` import extensions, and trailing commas in multiline declarations. Use `camelCase` for values/functions, `PascalCase` for React components and exported types, and `UPPER_SNAKE_CASE` for configuration keys. Keep protocol, bridge, and UI transformations in their focused modules. No formatter or linter is configured; match adjacent code and rely on TypeScript plus review.

## Testing Guidelines

Use `node:test` with `node:assert/strict`. Name files `<module>.test.ts` and write behavior-oriented test names. Add regression coverage for protocol payloads, redaction, Origin/capability checks, retries, and state transitions. There is no numeric coverage gate, but changed branches and security boundaries should be exercised.

## Commit & Pull Request Guidelines

Use concise Conventional Commit subjects seen in history, such as `feat(web): refine session experience` or `fix: support modern SEA builds`. PRs should explain user-visible behavior, affected Admin/end-user layer, verification commands, and linked issues. Include screenshots for UI changes and call out protocol, authentication, or configuration changes explicitly.

## Security & Configuration

Never commit OAuth codes, STS tokens, Endpoint query strings, or local config caches. Keep the bridge loopback-only and preserve Host/Origin checks, HttpOnly capability cookies, URL redaction, and ToolId/SessionId routing. Configure local runtime values with `npm start -- config`; do not introduce credential environment variables.

# Bootleg Cheeseburger - hub

The hub reads this at session start (`/blc:hub`); `/blc:brief` is the delegation playbook. Workers do not need it. It states the current rule, never a log: a ruling goes to the owning doc's `## Decisions`.

**Scope: sales and the Paddle integration.** The store card and checkout, pricing and localisation, the legal pages Paddle requires, the serial worker, and the Paddle account path from sandbox to live. Site layout, showcase and hosting work belongs to a plain chat unless it serves a sale.

## Session start

- Note the branch. Cloudflare Pages deploys `main` on push, so work on another branch is not live until the user merges and pushes it. The store is built on `stasis-store`.

## How work runs

- **A static site, no build step and no test suite.** Pages are hand-written HTML (`index.html` plus `terms.html`, `privacy.html`, `refunds.html`) sharing `style.css`; Vite only serves it locally.
- **Workers**: an Opus builder edits pages and commits its own files (`git commit -o`); two builders never touch `index.html` at once. Research (Paddle, DNS, hosting) goes to a Sonnet worker.
- **The gate** is the shop pre-commit hooks (gitleaks among them). Paddle client-side tokens are public by design; their line carries `// gitleaks:allow`. Server API keys never enter the repo.
- **The walk-through is the user's**: `just serve`, and `just preview` to see drafts (`?preview`). The hub adds a test drive line for each visible change.
- **Landing**: pushing is the user's (`just push`). Avoid `just ship`: it runs `git add -A`, which breaks the commit-own-paths rule.
- **The board is local only**: origin is public, so the epiq state worktree has a dead pushurl. Never `git push --all` or `--mirror`, and never point the state branch at origin.

## Where things live

- The store: the `STORE` block near the end of `index.html` (Paddle env, client token, price, serial worker URL). Paddle runs in sandbox until the user rules otherwise.
- The serial worker (Paddle webhook -> Keygen license -> Resend email, refund suspends): `~/Code/apps/stasis/store/worker`, a Cloudflare Worker in the Stasis repo, which has no board. Its setup runbook and the sale flow are `~/Code/apps/stasis/store/README.md`. A worker job there follows that repo's CLAUDE.md, commits there, and gates on `npm test` in `store/worker`; the item stays on this board. Deploying it (`npm run deploy`) and setting its secrets are the user's.
- Paddle tools: the `paddle-sandbox` MCP reads and writes the sandbox account; `paddle-live` and `paddle-docs` need the user to authorise them (`/mcp`). The `paddle:*` skills assume Next.js; take their Paddle facts, not their framework. Anything in the live account, and every dashboard-only step, is a `user` item.
- Product cards: the showcase sections of `index.html`; images in `assets/`.
- Legal copy: `terms.html`, `privacy.html`, `refunds.html`. Security policy: `SECURITY.md`.
- Recipes: `justfile` (`serve`, `preview`, `live`, `dns`) plus the shared blc recipes.

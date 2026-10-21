# Bootleg Cheeseburger - hub

The hub reads this at session start (`/blc:hub`); `/blc:brief` is the delegation playbook. Workers do not need it. It states the current rule, never a log: a ruling goes to the owning doc's `## Decisions`.

## Session start

- Note the branch. Cloudflare Pages deploys `main` on push, so work on another branch is not live until the user merges and pushes it.

## How work runs

- **A static site, no build step and no test suite.** Pages are hand-written HTML (`index.html` plus `terms.html`, `privacy.html`, `refunds.html`) sharing `style.css`; Vite only serves it locally.
- **Workers**: an Opus builder edits pages and commits its own files (`git commit -o`); two builders never touch `index.html` at once. Research (Paddle, DNS, hosting) goes to a Sonnet worker.
- **The gate** is the shop pre-commit hooks (gitleaks among them). Paddle client-side tokens are public by design; their line carries `// gitleaks:allow`. Server API keys never enter the repo.
- **The walk-through is the user's**: `just serve`, and `just preview` to see drafts (`?preview`). The hub adds a test drive line for each visible change.
- **Landing**: pushing is the user's (`just push`). Avoid `just ship`: it runs `git add -A`, which breaks the commit-own-paths rule.
- **The board is WWW in `~/Code/blc`**: this repo holds no epiq state; every epiq call passes `repoRoot=~/Code/blc`.

## Where things live

- The store: the `STORE` block near the end of `index.html` (Paddle env, client token, price, serial worker URL). The STORE team (`~/Code/store`, teams in `~/Code/blc/docs/agents.md`) specifies it, the Buy button, the price display and the legal copy Paddle relies on; check with STORE before changing them.
- Product cards: the showcase sections of `index.html`; images in `assets/`.
- Legal copy: `terms.html`, `privacy.html`, `refunds.html`. Security policy: `SECURITY.md`.
- Recipes: `justfile` (`serve`, `preview`, `live`, `dns`) plus the shared blc recipes.

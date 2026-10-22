# Bootleg Cheeseburger - hub

The hub reads this at session start (`/blc:hub`); `/blc:brief` is the delegation playbook. Workers do not need it. It states the current rule, never a log: a ruling goes to the owning doc's `## Decisions`.

## Session start

- Note the branch. Cloudflare Pages deploys `main` on push, so work on another branch is not live until the user merges and pushes it.

## How work runs

- **A static site, no build step and no test suite.** Pages are hand-written HTML (`index.html` plus `terms.html`, `privacy.html`, `refunds.html`) sharing `style.css`; Vite only serves it locally.
- **Workers**: an Opus builder edits pages and commits its own files (`git commit -o`); two builders never touch `index.html` at once. Research (Paddle, DNS, hosting) goes to a Sonnet worker.
- **The gate** is the shop pre-commit hooks (gitleaks among them). Paddle client-side tokens are public by design; their line carries `// gitleaks:allow`. Server API keys never enter the repo.
- **The walk-through is the user's**: `just run`, and `just dev-preview` to see drafts (`?preview`). The hub adds a test drive line for each visible change.
- **Landing**: pushing is the user's (`just push`).
- **The board is WWW in `~/Code/blc`**: this repo holds no epiq state; every epiq call passes `repoRoot=~/Code/blc`.

## Where things live

- The store: the `STORE` block near the end of `index.html` (Paddle env, client token, price, serial worker URL). The STORE team (`~/Code/store`, teams in `~/Code/blc/docs/agents.md`) specifies it, the Buy button, the price display and the legal copy Paddle relies on; check with STORE before changing them.
- Product cards: the showcase sections of `index.html`; images in `assets/`.
- Legal copy: `terms.html`, `privacy.html`, `refunds.html`. Security policy: `SECURITY.md`.
- EULAs: `eula/<app>.txt` (current) and `eula/<app>/<id>.txt` (every version, never removed), copied from `~/Code/store/eula` by `just tool-eula <app>`, never hand-edited. The id is STORE's `eula_version`; the recipe also rewrites the STORE block's `EULA_VERSION: "<id>", // eula:<app>` line.
- EULA drift rule: for every app `~/Code/store/gen/apps.json` gives `eula: "shared"`, the site copy, its versioned copy and its tagged `EULA_VERSION` match the store's text; `scripts/eula-check.py` enforces it in `just dev-check` and `.githooks/pre-push` (checks each pushed commit, so a drifted tree never deploys).
- Share links: each public app's copy-link button gives `/<app>`, a page (`<app>.html`) whose Open Graph tags unfurl as its card (`assets/share/<app>.png`; the site's is `site.png`). `just tool-share-cards [app]` regenerates pages and cards from `scripts/share/card.html` and the store catalog's `tagline`; never hand-edit them.
- Contact: the masthead "Contact" link on every page goes to `/contact` (`contact.html`), the one contact place: pick a category, then an app, and it opens a mailto precomputed from `~/Code/store/gen/contact.json` by `just tool-contact` (`scripts/contact-gen.py`, between the page's `contact:gen` markers, never hand-edited); `scripts/contact-check.py` fails a stale page in `just dev-check` and `.githooks/pre-push`.
- Redirects: `_redirects` serves `updates.bootlegcheeseburger.com` (`/<app>/latest.dmg`, `/<app>/appcast.xml`), one line per app per shape.
- Recipes: `justfile` (`run`, `dev-preview`, `dev-status`, `dev-check`, `tool-live`, `tool-dns`, `tool-eula`, `tool-share-cards`, `tool-contact`) plus the shared blc recipes.

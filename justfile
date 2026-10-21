# Bootleg Cheeseburger - static site tasks
# Cloudflare Pages auto-deploys `main`, so pushing `main` is the deploy (`just push`).

# serve the site locally with live-reload (vite HMR)

import? '~/Code/blc/just/core.just'

serve port="8000":
    npx vite --port {{port}}

# open the live site
live:
    open https://bootlegcheeseburger.com

# open local preview with drafts visible (needs `just serve` running)
preview port="8000":
    open "http://localhost:{{port}}/?preview"

# short git status
status:
    git status -s

# DNS / DNSSEC sanity check
dns:
    @echo "A records:"  && dig +short bootlegcheeseburger.com
    @echo "DS (registry):" && dig +short DS bootlegcheeseburger.com
    @echo "header flags:"  && dig +dnssec bootlegcheeseburger.com | grep -E 'status:|flags:'

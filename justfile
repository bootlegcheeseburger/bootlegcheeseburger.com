# Bootleg Cheeseburger - static site tasks
# Cloudflare Pages auto-deploys `main`, so `just ship` is the deploy.

# list recipes
default:
    @just --list

# serve the site locally with live-reload (vite HMR)
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

# commit everything and push (this triggers the Cloudflare Pages deploy)
ship msg:
    git add -A
    git commit -m "{{msg}}"
    git push

# DNS / DNSSEC sanity check
dns:
    @echo "A records:"  && dig +short bootlegcheeseburger.com
    @echo "DS (registry):" && dig +short DS bootlegcheeseburger.com
    @echo "header flags:"  && dig +dnssec bootlegcheeseburger.com | grep -E 'status:|flags:'

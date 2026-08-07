#!/usr/bin/env bash
#
# EARN study platform — one script to run the whole Docker stack.
#
#   ./run.sh up            Build (if needed) and start everything in the background
#   ./run.sh down          Stop and remove containers (keeps the database)
#   ./run.sh restart       Restart the whole stack
#   ./run.sh stop          Stop containers without removing them
#   ./run.sh start         Start previously-stopped containers
#   ./run.sh rebuild       Rebuild images from scratch and start
#   ./run.sh reset         WIPE the database volume and start fresh (re-seeds)
#   ./run.sh logs [svc]    Follow logs (optionally for one service: backend|web|db)
#   ./run.sh ps            Show container status
#   ./run.sh seed          Re-run the newsletter/researcher seed
#   ./run.sh migrate       Apply database migrations
#   ./run.sh superuser     Create a Django superuser (interactive)
#   ./run.sh manage <...>  Run any Django manage.py command in the backend
#   ./run.sh shell         Open a shell inside the backend container
#   ./run.sh help          Show this help
#
set -euo pipefail

cd "$(dirname "$0")"

# --- Pretty output ---------------------------------------------------------
c_reset='\033[0m'; c_green='\033[0;32m'; c_blue='\033[0;34m'
c_yellow='\033[0;33m'; c_red='\033[0;31m'
info()  { printf "${c_blue}▶ %s${c_reset}\n" "$*"; }
ok()    { printf "${c_green}✓ %s${c_reset}\n" "$*"; }
warn()  { printf "${c_yellow}! %s${c_reset}\n" "$*"; }
err()   { printf "${c_red}✗ %s${c_reset}\n" "$*" >&2; }

# --- Detect docker compose -------------------------------------------------
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  err "Docker Compose not found. Install Docker Desktop or the compose plugin."
  exit 1
fi

# --- Ensure .env exists, then load it for port display ---------------------
if [ ! -f .env ]; then
  cp .env.example .env
  warn "Created .env from .env.example (review ports, credentials, and LOCAL_LLM_BASE_URL)."
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a
WEB_PORT="${WEB_PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8001}"

urls() {
  echo
  ok "EARN is up:"
  echo "    Participant site : http://localhost:${WEB_PORT}"
  echo "    Researcher login : http://localhost:${WEB_PORT}/researcher/login"
  echo "    API + docs       : http://localhost:${BACKEND_PORT}/api/docs/"
  echo "    Researcher user  : ${RESEARCHER_USERNAME:-researcher} (password is in .env)"
  echo
}

wait_for_backend() {
  info "Waiting for the backend to become healthy…"
  for _ in $(seq 1 60); do
    if curl -fsS "http://localhost:${BACKEND_PORT}/api/health/" >/dev/null 2>&1; then
      ok "Backend is healthy."
      return 0
    fi
    sleep 2
  done
  warn "Backend did not respond in time — check './run.sh logs backend'."
}

cmd="${1:-help}"; shift || true

case "$cmd" in
  up|start-build)
    info "Building and starting the stack…"
    $DC up -d --build --remove-orphans
    wait_for_backend
    urls
    ;;
  down)
    info "Stopping and removing containers (database volume kept)…"
    $DC down --remove-orphans
    ok "Stopped."
    ;;
  restart)
    info "Restarting the stack…"
    $DC down --remove-orphans
    $DC up -d --build --remove-orphans
    wait_for_backend
    urls
    ;;
  stop)
    $DC stop
    ok "Containers stopped (use './run.sh start' to resume)."
    ;;
  start)
    $DC start
    wait_for_backend
    urls
    ;;
  rebuild)
    info "Rebuilding images from scratch…"
    $DC build --no-cache
    $DC up -d --remove-orphans
    wait_for_backend
    urls
    ;;
  reset)
    warn "This DELETES all collected data (the database volume)."
    printf "Type 'yes' to continue: "; read -r confirm
    if [ "$confirm" = "yes" ]; then
      $DC down -v --remove-orphans
      $DC up -d --build --remove-orphans
      wait_for_backend
      urls
    else
      info "Cancelled."
    fi
    ;;
  logs)
    $DC logs -f "${@:-}"
    ;;
  ps|status)
    $DC ps
    ;;
  seed)
    $DC exec backend python manage.py seed_study
    ;;
  migrate)
    $DC exec backend python manage.py migrate
    ;;
  superuser)
    $DC exec backend python manage.py createsuperuser
    ;;
  manage)
    $DC exec backend python manage.py "$@"
    ;;
  shell)
    $DC exec backend bash
    ;;
  help|-h|--help)
    # Print the leading comment block (skip the shebang) as usage text.
    awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
    ;;
  *)
    err "Unknown command: $cmd"
    echo "Run './run.sh help' for usage."
    exit 1
    ;;
esac

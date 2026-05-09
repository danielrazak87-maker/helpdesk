#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# KF Helpdesk — Production Startup Script (gunicorn)
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   ./start.sh              # Start gunicorn in foreground (Ctrl-C to stop)
#   ./start.sh --daemon     # Start gunicorn as a background daemon
#   ./start.sh --reload     # Start with auto-reload (development)
#   ./start.sh --stop       # Stop a running daemon
#   ./start.sh --status     # Check if the daemon is running
#
# For production deployment, prefer the systemd service:
#   systemctl start helpdesk
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/helpdesk"
VENV_DIR="$SCRIPT_DIR/.venv"
PID_FILE="/run/helpdesk.pid"
LOG_DIR="/var/log/helpdesk"
GUNICORN="$VENV_DIR/bin/gunicorn"

# ── helpers ──────────────────────────────────────────────────────────

_ensure_dirs() {
    mkdir -p "$LOG_DIR"
}

_load_env() {
    if [ -f "$PROJECT_DIR/.env" ]; then
        set -a
        # shellcheck source=/dev/null
        source "$PROJECT_DIR/.env"
        set +a
    fi
}

_status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        local pid
        pid=$(cat "$PID_FILE")
        echo "Helpdesk gunicorn is RUNNING (pid $pid)"
        return 0
    else
        echo "Helpdesk gunicorn is STOPPED"
        return 1
    fi
}

# ── main ─────────────────────────────────────────────────────────────

_ensure_dirs
_load_env

MODE="${1:-foreground}"

case "$MODE" in
    --daemon|-d)
        echo "Starting gunicorn in daemon mode..."
        cd "$PROJECT_DIR"
        exec "$GUNICORN" wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers 4 \
            --worker-class sync \
            --worker-tmp-dir /dev/shm \
            --timeout 120 \
            --graceful-timeout 30 \
            --keep-alive 5 \
            --max-requests 1200 \
            --max-requests-jitter 50 \
            --access-logfile "$LOG_DIR/access.log" \
            --error-logfile "$LOG_DIR/error.log" \
            --log-level info \
            --pid "$PID_FILE" \
            --daemon \
            --name helpdesk
        echo "Done. Check status with: $0 --status"
        ;;

    --reload|-r)
        echo "Starting gunicorn with auto-reload (development mode)..."
        cd "$PROJECT_DIR"
        exec "$GUNICORN" wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers 1 \
            --worker-class sync \
            --timeout 120 \
            --reload \
            --access-logfile - \
            --error-logfile - \
            --log-level debug
        ;;

    --stop)
        if [ -f "$PID_FILE" ]; then
            local pid
            pid=$(cat "$PID_FILE")
            echo "Stopping helpdesk gunicorn (pid $pid)..."
            kill -TERM "$pid" 2>/dev/null || true
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                echo "Graceful stop failed, forcing..."
                kill -KILL "$pid" 2>/dev/null || true
            fi
            rm -f "$PID_FILE"
            echo "Stopped."
        else
            echo "No PID file found — nothing to stop."
        fi
        ;;

    --status|-s)
        _status
        ;;

    foreground|"")
        echo "Starting gunicorn in foreground (Ctrl-C to stop)..."
        echo "Logs: $LOG_DIR/"
        cd "$PROJECT_DIR"
        exec "$GUNICORN" wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers 4 \
            --worker-class sync \
            --worker-tmp-dir /dev/shm \
            --timeout 120 \
            --graceful-timeout 30 \
            --keep-alive 5 \
            --max-requests 1200 \
            --max-requests-jitter 50 \
            --access-logfile "$LOG_DIR/access.log" \
            --error-logfile "$LOG_DIR/error.log" \
            --log-level info \
            --pid "$PID_FILE" \
            --name helpdesk
        ;;

    *)
        echo "Usage: $0 [--daemon|--reload|--stop|--status]"
        echo ""
        echo "  (no arg)      Start in foreground"
        echo "  --daemon, -d  Start as background daemon"
        echo "  --reload, -r  Start with auto-reload (dev)"
        echo "  --stop        Stop a running daemon"
        echo "  --status, -s  Check if daemon is running"
        exit 1
        ;;
esac

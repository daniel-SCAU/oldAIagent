#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="system_test.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "===== System Test Report: $(date) ====="

# Helper to check command availability
check_command() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "[OK] $cmd found: $(command -v "$cmd")"
    else
        echo "[WARN] $cmd not found"
    fi
}

# System information
section_system_info() {
    echo "\n--- System Information ---"
    uname -a
    if command -v lsb_release >/dev/null 2>&1; then
        lsb_release -a || true
    fi
}

# CPU information
section_cpu_info() {
    echo "\n--- CPU Information ---"
    if command -v lscpu >/dev/null 2>&1; then
        lscpu
    else
        cat /proc/cpuinfo
    fi
}

# Memory information
section_memory_info() {
    echo "\n--- Memory Information ---"
    free -h || true
}

# Disk usage
section_disk_usage() {
    echo "\n--- Disk Usage ---"
    df -h
}

# Network connectivity
section_network() {
    echo "\n--- Network Connectivity ---"
    check_command curl
    if command -v curl >/dev/null 2>&1; then
        curl -I https://example.com 2>/dev/null | head -n 1 || true
    fi
    check_command ping
    if command -v ping >/dev/null 2>&1; then
        ping -c 1 8.8.8.8 >/dev/null && echo "Ping to 8.8.8.8 successful" || echo "Ping failed"
    fi
}

# Environment variables of interest
section_env_vars() {
    echo "\n--- Environment Variables ---"
    env | sort
}

# Python environment
section_python() {
    echo "\n--- Python Environment ---"
    check_command python
    if command -v python >/dev/null 2>&1; then
        python --version
        python - <<'PYEOF'
import sys, pkgutil
print('Executable:', sys.executable)
print('Installed packages (first 50):')
for i, p in enumerate(pkgutil.iter_modules()):
    if i >= 50:
        print('...')
        break
    print(' -', p.name)
PYEOF
    fi
}

# File I/O test
section_file_io() {
    echo "\n--- File I/O Test ---"
    tmpfile=$(mktemp)
    echo "Temporary file created at $tmpfile"
    echo "hello" > "$tmpfile"
    cat "$tmpfile"
    rm "$tmpfile"
    echo "Temporary file removed"
}

# Port check
section_ports() {
    echo "\n--- Listening Ports ---"
    if command -v ss >/dev/null 2>&1; then
        ss -tuln
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln
    else
        echo "ss or netstat not available"
    fi
}

# Curl API endpoints to verify responses
section_endpoints() {
    echo "\n--- API Endpoint Checks ---"
    if ! command -v curl >/dev/null 2>&1; then
        echo "curl not installed"
        return
    fi

    # Test FastAPI app if uvicorn available
    if command -v uvicorn >/dev/null 2>&1; then
        echo "Starting FastAPI app on port 8000"
        uvicorn app:app --port 8000 --log-level warning &
        uvicorn_pid=$!
        sleep 2
        local url="http://127.0.0.1:8000/health"
        echo "GET $url"
        curl -s -o /dev/null -w "HTTP %{http_code}\n" "$url" || echo "Failed to reach $url"
        kill "$uvicorn_pid"
        wait "$uvicorn_pid" 2>/dev/null || true
    else
        echo "uvicorn not installed; skipping FastAPI endpoint test"
    fi

    # Test Flask server
    if command -v python >/dev/null 2>&1; then
        echo "Starting Flask server on port 5000"
        python server.py >/tmp/flask_server.log 2>&1 &
        flask_pid=$!
        sleep 2
        local url="http://127.0.0.1:5000/status"
        echo "GET $url"
        curl -s -o /dev/null -w "HTTP %{http_code}\n" "$url" || echo "Failed to reach $url"
        kill "$flask_pid"
        wait "$flask_pid" 2>/dev/null || true
    fi
}

# Run project tests if pytest available
section_pytests() {
    echo "\n--- Running Pytest ---"
    if command -v pytest >/dev/null 2>&1; then
        pytest || echo "Pytest returned non-zero exit code"
    else
        echo "pytest not installed"
    fi
}

# Main
section_system_info
section_cpu_info
section_memory_info
section_disk_usage
section_network
section_env_vars
section_python
section_file_io
section_ports
section_endpoints
section_pytests

echo "\n===== End of Report ====="

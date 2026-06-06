#!/bin/sh
set -e

echo "============================================"
echo "  Emergency-Backup — Railway Deploy"
echo "  Main API: Razorpay Gateway (autorz)"
echo "  Port: ${PORT:-8000}"
echo "============================================"

# Load .env if present (Railway injects vars directly, but .env fallback for local)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Start main Razorpay API
exec python3 autorz/autorz.py

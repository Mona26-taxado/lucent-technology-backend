#!/usr/bin/env bash
# Run from your Mac (NOT from the Ubuntu server SSH session).
set -euo pipefail

HOST="${1:-root@187.127.140.218}"
REMOTE_DIR="${2:-/var/www/lucent_backend}"
LOCAL_BACKEND="$(cd "$(dirname "$0")/.." && pwd)"

echo "Deploying PDF fix from: $LOCAL_BACKEND"
echo "To: $HOST:$REMOTE_DIR"

scp \
  "$LOCAL_BACKEND/app/templates/certificate.html" \
  "$HOST:$REMOTE_DIR/app/templates/certificate.html"

scp \
  "$LOCAL_BACKEND/app/services/pdf_service.py" \
  "$HOST:$REMOTE_DIR/app/services/pdf_service.py"

scp \
  "$LOCAL_BACKEND/app/schemas/template.py" \
  "$HOST:$REMOTE_DIR/app/schemas/template.py"

scp \
  "$LOCAL_BACKEND/app/main.py" \
  "$HOST:$REMOTE_DIR/app/main.py"

ssh "$HOST" "grep -n '69%; top: 84.2%' $REMOTE_DIR/app/templates/certificate.html && systemctl restart lucent-backend && systemctl is-active lucent-backend"

echo "Done. Open certificate → Print (regenerates PDF)."

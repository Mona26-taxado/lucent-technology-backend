#!/usr/bin/env bash
# Run on the Linux production server (as the same user that runs uvicorn).
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -f ../venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source ../venv/bin/activate
fi

echo "Installing Playwright Chromium + OS deps..."
python -m playwright install --with-deps chromium

echo "Verifying Chromium launch..."
python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    print("OK", browser.version)
    browser.close()
PY

echo "Done. Restart the API service, then try Print/Download PDF again."

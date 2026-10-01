#!/usr/bin/env bash
# Prove the public address is private by default: the home page sends an anonymous visitor to
# the login page, the login page serves its form, the health check still answers, and a role page
# (/admin) sends an anonymous visitor to the login page too.
#
# Run by the release after the new commit is confirmed live. It reads only public responses, so
# it needs no credential and prints none. Redirects are observed, never followed (no `-L`).
# Contract: specs/004-email-otp-auth/contracts/pipeline.md#scriptsverify_privatesh and
# specs/005-roles-authorization/contracts/pipeline.md#scriptsverify_privatesh-changed
#
# Usage:  ./scripts/verify_private.sh <base-url>
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <base-url>" >&2
  exit 2
fi

# Tolerate a trailing slash in PUBLIC_BASE_URL rather than producing `//login`.
BASE_URL="${1%/}"

# A free instance may be spinning up from cold: retry for up to a minute, and allow a single
# request to take a while.
DEADLINE_SECONDS=60
RETRY_INTERVAL=5
REQUEST_TIMEOUT=60

body=$(mktemp)
headers=$(mktemp)
trap 'rm -f "$body" "$headers"' EXIT

# The outcome of the last check, printed if the deadline passes.
failure=""

# GET <url> into $body and $headers; print the HTTP status (000 when there was no response).
fetch() {
  local status
  : >"$body"
  : >"$headers"
  # On a failed connection curl prints 000 and exits non-zero; `|| status=…` replaces the value
  # rather than appending to it.
  status=$(
    curl -sS -o "$body" -D "$headers" -w '%{http_code}' --max-time "$REQUEST_TIMEOUT" "$1" \
      2>/dev/null
  ) || status="000"
  echo "$status"
}

location() {
  sed -n 's/^[Ll]ocation:[[:space:]]*\(.*\)$/\1/p' "$headers" | tr -d '\r' | head -n 1
}

report() {
  local url="$1" status="$2" problem="$3"
  failure="GET ${url}: ${problem}
  status:   ${status}
  location: $(location)
  body:     $(head -c 500 "$body")"
}

# GET <path> anonymously; succeed only on a 303 whose Location ends in /login?next=<encoded path>.
check_redirects_to_login() {
  local path="$1" encoded="$2" url="${BASE_URL}$1" status
  status=$(fetch "$url")
  if [ "$status" != "303" ]; then
    report "$url" "$status" "expected 303 to the login page"
    return 1
  fi
  case "$(location)" in
    */login\?next="$encoded") ;;
    *)
      report "$url" "$status" "expected Location ending in /login?next=${encoded}"
      return 1
      ;;
  esac
  echo "GET ${url} → 303, Location: $(location)"
}

check_home_redirects() {
  check_redirects_to_login / %2F
}

check_admin_redirects() {
  check_redirects_to_login /admin %2Fadmin
}

check_login_form() {
  local url="${BASE_URL}/login" status
  status=$(fetch "$url")
  if [ "$status" != "200" ]; then
    report "$url" "$status" "expected 200 with the email form"
    return 1
  fi
  if ! grep -q 'name="email"' "$body" || ! grep -q 'action="/login"' "$body"; then
    report "$url" "$status" "the page has no email form posting to /login"
    return 1
  fi
  echo "GET ${url} → 200, email form present"
}

check_health() {
  local url="${BASE_URL}/healthz" status
  status=$(fetch "$url")
  if [ "$status" != "200" ]; then
    report "$url" "$status" "expected 200"
    return 1
  fi
  echo "GET ${url} → 200"
}

started_at=$(date +%s)
while true; do
  if check_home_redirects && check_login_form && check_health && check_admin_redirects; then
    echo "Access control verified: the site is private by default."
    exit 0
  fi
  elapsed=$(($(date +%s) - started_at))
  if [ "$elapsed" -ge "$DEADLINE_SECONDS" ]; then
    echo "error: access control not verified within ${DEADLINE_SECONDS}s." >&2
    echo "$failure" >&2
    exit 1
  fi
  echo "[${elapsed}s] not yet: $(printf '%s' "$failure" | head -n 1); retrying…"
  sleep "$RETRY_INTERVAL"
done

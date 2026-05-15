#!/bin/bash
# Mismo flujo que debug_login.py pero usando curl real (HTTP/2 + TLS de libcurl).
# Si esto entra y urllib no, CheckJC nos detecta por TLS/HTTP fingerprint.
#
# Uso:
#   ./debug_login_curl.sh USER PASSWORD SUBDOMAIN

set -e

USER="${1:?usage: $0 USER PASSWORD SUBDOMAIN}"
PASS="${2:?usage: $0 USER PASSWORD SUBDOMAIN}"
SUB="${3:?usage: $0 USER PASSWORD SUBDOMAIN}"

BASE="https://${SUB}.checkjc.com"
URL="${BASE}/login"
COOK="/tmp/jc_curl_cookies.txt"
HTMLF="/tmp/jc_curl_login.html"

rm -f "$COOK" "$HTMLF"

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'

echo "GET $URL (HTTP/2)..."
curl --http2 -sS -c "$COOK" -o "$HTMLF" -w "  status %{http_code}, size %{size_download}, http_version %{http_version}\n" \
  -H "User-Agent: $UA" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" \
  -H "Accept-Language: es-ES,es;q=0.9" \
  -H "Sec-Ch-Ua: \"Google Chrome\";v=\"147\", \"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"147\"" \
  -H 'Sec-Ch-Ua-Mobile: ?0' \
  -H 'Sec-Ch-Ua-Platform: "macOS"' \
  -H 'Sec-Fetch-Dest: document' \
  -H 'Sec-Fetch-Mode: navigate' \
  -H 'Sec-Fetch-Site: none' \
  -H 'Sec-Fetch-User: ?1' \
  -H 'Upgrade-Insecure-Requests: 1' \
  "$URL"

TOKEN=$(grep -oE 'name="token" value="[^"]+"' "$HTMLF" | head -1 | sed 's/.*value="\([^"]*\)".*/\1/')
USERF=$(grep -oE 'class="[^"]*form_username[^"]*"[^>]*name="[^"]+"' "$HTMLF" | head -1 | sed 's/.*name="\([^"]*\)".*/\1/')
PASSF=$(grep -oE 'class="[^"]*form_password[^"]*"[^>]*name="[^"]+"' "$HTMLF" | head -1 | sed 's/.*name="\([^"]*\)".*/\1/')

echo "  token = ${TOKEN:0:30}..."
echo "  user_field = $USERF"
echo "  pass_field = $PASSF"

echo ""
echo "POST $URL (HTTP/2)..."
curl --http2 -sS -b "$COOK" -c "$COOK" --max-redirs 0 -o /tmp/jc_curl_post_body.html \
  -w "  status %{http_code}, http_version %{http_version}, size %{size_download}, redirect %{redirect_url}\n" \
  -D /tmp/jc_curl_resp_headers.txt \
  -H "User-Agent: $UA" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7" \
  -H "Accept-Language: es-ES,es;q=0.9" \
  -H "Cache-Control: max-age=0" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Origin: $BASE" \
  -H "Referer: $URL" \
  -H "Sec-Ch-Ua: \"Google Chrome\";v=\"147\", \"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"147\"" \
  -H 'Sec-Ch-Ua-Mobile: ?0' \
  -H 'Sec-Ch-Ua-Platform: "macOS"' \
  -H 'Sec-Fetch-Dest: document' \
  -H 'Sec-Fetch-Mode: navigate' \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'Sec-Fetch-User: ?1' \
  -H 'Upgrade-Insecure-Requests: 1' \
  --data-urlencode "token=$TOKEN" \
  --data-urlencode "$USERF=$USER" \
  --data-urlencode "$PASSF=$PASS" \
  --data-urlencode "btn-login=" \
  "$URL"

echo ""
echo "Response headers (Location / Set-Cookie):"
grep -iE "^(location|set-cookie):" /tmp/jc_curl_resp_headers.txt || echo "  (none)"

echo ""
echo "Body analysis of POST response:"
if grep -qi "form-login" /tmp/jc_curl_post_body.html; then
    echo "  ❌ Body contains the login form again → login rechazado"
elif grep -qi "portal-host\|btn-check\|GONZALEZ\|Fichar" /tmp/jc_curl_post_body.html; then
    echo "  ✅ Body looks like the dashboard → login OK"
else
    echo "  ⚠️  Unknown body content. First 500 chars:"
    head -c 500 /tmp/jc_curl_post_body.html
    echo ""
fi

echo ""
echo "Following with GET /portal/employee to confirm session..."
curl --http2 -sS -b "$COOK" -o /tmp/jc_curl_portal.html \
  -w "  status %{http_code}, size %{size_download}, redirect %{redirect_url}\n" \
  -H "User-Agent: $UA" \
  "${BASE}/portal/employee"

if grep -qi "form-login" /tmp/jc_curl_portal.html; then
    echo "  ❌ Portal returned the login form → session NOT established"
elif grep -qi "btn-check\|Fichar\|GONZALEZ" /tmp/jc_curl_portal.html; then
    echo "  ✅ Portal returned the dashboard → SESSION OK"
else
    echo "  ⚠️  Unknown portal response. First 500 chars:"
    head -c 500 /tmp/jc_curl_portal.html
fi

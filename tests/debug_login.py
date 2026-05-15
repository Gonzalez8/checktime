"""
Debug del login contra CheckJC sin Playwright y sin pasar por BD.
Usa solo urllib (stdlib) para descartar problemas del cliente HTTP.

Uso desde el contenedor `app`:
    python tests/debug_login.py 47779708z Oriotif90 trainingbnetwork

Salida esperada:
- "STATUS 302 LOC .../portal/employee"  -> Login OK
- "STATUS 302 LOC .../login"            -> Rechazo silencioso (IP marcada o creds)
- "STATUS 200 LOC None"                 -> Mismo rechazo, server devuelve la pagina de login
"""
import sys
import re
import urllib.request
import urllib.parse
import http.cookiejar


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Evita que urllib siga el 302 automaticamente, para poder leer el Location."""
    def redirect_request(self, *args, **kwargs):
        return None


def main(user, password, subdomain):
    base = f"https://{subdomain}.checkjc.com"
    login_url = f"{base}/login"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
    )
    opener.addheaders = [("User-Agent", UA)]

    print(f"GET {login_url}")
    html = opener.open(login_url).read().decode("utf-8", errors="ignore")
    print(f"  body length: {len(html)}")

    # Banner de IP bloqueada?
    if "ha sido bloqueada" in html.lower():
        m = re.search(r"dentro de\s+(\d+)\s+minutos", html, re.IGNORECASE)
        print(f"  !! IP BLOCKED banner found ({m.group(1) if m else '?'} min)")

    token = re.search(r'name="token"\s+value="([^"]+)"', html).group(1)
    user_field = re.search(r'class="[^"]*form_username[^"]*"[^>]*name="([^"]+)"', html).group(1)
    pass_field = re.search(r'class="[^"]*form_password[^"]*"[^>]*name="([^"]+)"', html).group(1)
    print(f"  token[:30] = {token[:30]}...")
    print(f"  user_field = {user_field}")
    print(f"  pass_field = {pass_field}")

    data = urllib.parse.urlencode({
        "token": token,
        user_field: user,
        pass_field: password,
    }).encode()

    print(f"\nPOST {login_url}")
    req = urllib.request.Request(
        login_url,
        data=data,
        headers={
            "User-Agent": UA,
            "Origin": base,
            "Referer": login_url,
            "Content-Type": "application/x-www-form-urlencoded",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
        },
    )
    opener2 = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        NoRedirect(),
    )
    try:
        r = opener2.open(req)
        status = r.status
        location = r.headers.get("Location")
        body = r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        status = e.code
        location = e.headers.get("Location")
        body = e.read().decode("utf-8", errors="ignore")

    print(f"  STATUS: {status}")
    print(f"  LOCATION: {location!r}")
    print(f"  body length: {len(body)}")

    if location and "/login" not in location:
        print("\n  >>> LOGIN OK <<<")
    elif body and "ha sido bloqueada" in body.lower():
        m = re.search(r"dentro de\s+(\d+)\s+minutos", body, re.IGNORECASE)
        print(f"\n  >>> IP BLOCKED ({m.group(1) if m else '?'} min) <<<")
    else:
        print("\n  >>> REJECTED (no banner) <<<")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python debug_login.py <user> <password> <subdomain>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])

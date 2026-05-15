"""
Test del login usando curl_cffi (TLS fingerprint de Chrome exacto).
Si esto entra y urllib no, confirmamos que el problema es TLS fingerprint.

Uso:
    python tests/debug_login_curl_cffi.py 47779708Z Oriotif90 trainingbnetwork
"""
import sys
import re
from curl_cffi import requests


def main(user, password, subdomain):
    base = f"https://{subdomain}.checkjc.com"
    login_url = f"{base}/login"

    # impersonate="chrome147" hace que curl_cffi negocie TLS, HTTP/2 y headers
    # exactamente como Chrome 147. Es la diferencia clave con curl/urllib.
    session = requests.Session(impersonate="chrome")

    print(f"GET {login_url}")
    r = session.get(login_url)
    print(f"  status={r.status_code}, size={len(r.content)}, http_version={r.http_version}")
    html = r.text

    if "ha sido bloqueada" in html.lower():
        print("  !! IP BLOCKED banner present")

    token = re.search(r'name="token"\s+value="([^"]+)"', html).group(1)
    user_field = re.search(r'class="[^"]*form_username[^"]*"[^>]*name="([^"]+)"', html).group(1)
    pass_field = re.search(r'class="[^"]*form_password[^"]*"[^>]*name="([^"]+)"', html).group(1)
    print(f"  token[:30]={token[:30]}...")
    print(f"  user_field={user_field}")
    print(f"  pass_field={pass_field}")

    print(f"\nPOST {login_url}")
    r2 = session.post(
        login_url,
        data={
            "token": token,
            user_field: user,
            pass_field: password,
            "btn-login": "",
        },
        headers={
            "Origin": base,
            "Referer": login_url,
        },
        allow_redirects=False,
    )
    print(f"  status={r2.status_code}, size={len(r2.content)}")
    location = r2.headers.get("location") or r2.headers.get("Location")
    print(f"  Location: {location!r}")

    if location and "/login" not in location and location:
        print("\n  >>> LOGIN OK <<<")
        # Verifica con un GET al portal
        r3 = session.get(f"{base}/portal/employee", allow_redirects=False)
        print(f"  GET /portal/employee → status={r3.status_code}, "
              f"location={r3.headers.get('location')}, size={len(r3.content)}")
        if "btn-check" in r3.text or "GONZALEZ" in r3.text or "Fichar" in r3.text:
            print("  >>> Dashboard accesible — SESSION OK <<<")
    elif "ha sido bloqueada" in r2.text.lower():
        print("\n  >>> IP BLOCKED <<<")
    else:
        print("\n  >>> REJECTED (no banner) <<<")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python debug_login_curl_cffi.py USER PASS SUBDOMAIN")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])

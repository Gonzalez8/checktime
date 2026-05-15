import logging
import re
from playwright.sync_api import sync_playwright

from checktime.shared.config import get_selenium_timeout, get_simulation_mode

SIMULATION_MODE = get_simulation_mode()

logger = logging.getLogger(__name__)


class CheckJCError(Exception):
    """Base para todos los errores controlados de CheckJC."""


class CheckJCIPBlocked(CheckJCError):
    """CheckJC ha bloqueado el IP por demasiados intentos fallidos.
    Suele liberarse en ~10 minutos."""


class CheckJCLoginRejected(CheckJCError):
    """Login rechazado (302 a /login sin banner explícito de bloqueo).
    CheckJC no distingue desde fuera entre credenciales malas y rate-limit
    silencioso previo al lockout duro: ambos producen exactamente la misma
    respuesta. Por eso esta excepción no afirma cuál es la causa."""


class CheckJCSessionLost(CheckJCError):
    """La sesión expiró o el server forzó logout durante el check."""


class CheckJCFormError(CheckJCError):
    """No se pudo parsear el form del login o del dashboard.
    Indica un cambio en el HTML de CheckJC que rompe los selectores."""


class CheckJCUnexpectedResponse(CheckJCError):
    """Respuesta HTTP fuera de lo esperado (5xx, status raro, etc.)."""

# UA de Chrome reciente. Sin esto y sin los headers Sec-Fetch-*, el server
# de CheckJC (Server: IJCSVR) rechaza el POST de login en silencio (302 a /login).
_CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)


def _browser_headers(base_url, referer, sec_fetch_site="same-origin"):
    return {
        "User-Agent": _CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Origin": base_url,
        "Referer": referer,
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": sec_fetch_site,
        "Sec-Fetch-User": "?1",
    }


class CheckJCClient:
    """Cliente HTTP para CheckJC v7.4.

    CheckJC v7.4 migró el login a Stencil + Declarative Shadow DOM closed con
    nombres de campos aleatorios por render. Selenium ya no puede interactuar
    con el DOM. La solución es hacer POST HTTP directos contra los endpoints,
    reproduciendo lo que haría el navegador.

    Mantiene la misma interfaz pública que la versión Selenium para que el
    scheduler (service.py) no necesite cambios.
    """

    def __init__(self, username, password, subdomain):
        if not username or not password or not subdomain:
            raise ValueError("CheckJC username, password, and subdomain must be provided.")

        self.username = username
        self.password = password
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.checkjc.com"
        self.login_url = f"{self.base_url}/login"
        self.portal_url = f"{self.base_url}/portal/employee"

        self._pw = None
        self._request = None
        self._timeout_ms = get_selenium_timeout() * 1000

    def __enter__(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation mode enabled for {self.username}")
            return self

        # Playwright API HTTP sin lanzar navegador: usa solo el driver Node
        # que viene con `pip install playwright`. No requiere chromium binario.
        self._pw = sync_playwright().start()
        self._request = self._pw.request.new_context(
            user_agent=_CHROME_UA,
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"},
            timeout=self._timeout_ms,
        )
        logger.info(f"Playwright request context inicializado para {self.username}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._request:
            self._request.dispose()
        if self._pw:
            self._pw.stop()
        if self._request:
            logger.info(f"Playwright cerrado para {self.username}")

    def login(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation: Login successful for {self.username}")
            return True

        # 1) GET /login para obtener el form fresco (token + nombres random de campos)
        r = self._request.get(
            self.login_url,
            headers={
                **_browser_headers(self.base_url, self.login_url, sec_fetch_site="none"),
                "Sec-Fetch-Site": "none",
            },
        )
        if r.status != 200:
            raise CheckJCUnexpectedResponse(
                f"GET {self.login_url} returned status={r.status}"
            )
        login_html = r.text()

        # Si el IP está pre-bloqueado, el server ya muestra el banner en el GET.
        mins = self._ip_block_minutes(login_html)
        if mins is not None:
            raise CheckJCIPBlocked(
                f"CheckJC blocked this IP for {self.username}. "
                f"Retry available in {mins} minutes (per server)."
            )

        token, user_field, pass_field = self._extract_login_form(login_html)

        # 2) POST /login con el form
        r2 = self._request.post(
            self.login_url,
            form={
                "token": token,
                user_field: self.username,
                pass_field: self.password,
            },
            headers={
                **_browser_headers(self.base_url, self.login_url),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            max_redirects=0,
        )
        location = r2.headers.get("location", "")

        # Login OK: 302 a algo que NO sea /login.
        if r2.status == 302 and "/login" not in location:
            logger.info(f"Login successful for {self.username}, redirected to {location}")
            return True

        # 200 con body: el server devuelve la página de login otra vez.
        # Puede ser por IP bloqueada (con banner) o por credenciales malas
        # (sin banner, body puede tener el form vacío o estar vacío).
        body = r2.text() if r2.status == 200 else ""
        mins = self._ip_block_minutes(body) if body else None
        if mins is not None:
            raise CheckJCIPBlocked(
                f"CheckJC blocked this IP after failed attempts for {self.username}. "
                f"Retry available in {mins} minutes (per server)."
            )

        raise CheckJCLoginRejected(
            f"CheckJC rejected the login for {self.username} "
            f"(status={r2.status}, location={location!r}). "
            f"Cannot tell from the server response whether it's bad credentials "
            f"or silent rate-limit before the hard lockout. "
            f"Check if the user can log in via the web."
        )

    def perform_check(self, check_type: str):
        """Realiza un fichaje (entrada o salida).

        CheckJC v7.4 no distingue 'in' / 'out' en el POST: registra un check
        en el momento, el server decide si es entrada o salida según el último
        estado del usuario. El parámetro check_type se mantiene solo para
        compatibilidad con la interfaz anterior y para logging.
        """
        if SIMULATION_MODE:
            logger.info(f"Simulation: Check {check_type} completed for {self.username}")
            return True

        # 1) GET dashboard para extraer el rnd y validators activos
        r = self._request.get(
            self.portal_url,
            headers=_browser_headers(self.base_url, self.login_url),
        )
        # Si caímos en /login, la sesión se perdió entre login() y aquí.
        if r.url.endswith("/login") or (r.status == 200 and 'class="form-login' in r.text()):
            raise CheckJCSessionLost(
                f"Lost session before submitting check {check_type} for {self.username} "
                f"(GET portal redirected back to login)."
            )
        if r.status != 200:
            raise CheckJCUnexpectedResponse(
                f"GET {self.portal_url} returned status={r.status}"
            )

        check_form = self._extract_check_form(r.text())
        if not check_form:
            raise CheckJCFormError(
                f"No usable .form_check found in dashboard HTML for {self.username}. "
                f"This usually means CheckJC changed the dashboard layout."
            )

        # 2) POST de check con los campos del form correcto
        logger.info(
            f"Submitting check ({check_type}) for {self.username} "
            f"with validator={check_form['validator']}, rnd={check_form['rnd']}"
        )
        r2 = self._request.post(
            self.portal_url,
            form={
                "gps": "NA",  # sin geolocation (server context)
                "validator": check_form["validator"],
                "checkpoint_identifier": "",
                "rnd": check_form["rnd"],
            },
            headers={
                **_browser_headers(self.base_url, self.portal_url),
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            },
            max_redirects=0,
        )
        location = r2.headers.get("location", "")

        # Sesión perdida (401, o redirect a /login/logout).
        if r2.status == 401 or "/login" in location or "/logout" in location:
            raise CheckJCSessionLost(
                f"Session lost while submitting check {check_type} for {self.username} "
                f"(status={r2.status}, location={location!r})."
            )

        if r2.status not in (200, 302):
            raise CheckJCUnexpectedResponse(
                f"POST check returned unexpected status={r2.status}, location={location!r}"
            )

        logger.info(
            f"Check {check_type} completed for {self.username} "
            f"(status={r2.status}, validator={check_form['validator']})"
        )
        return True

    def check_in(self):
        return self.perform_check("in")

    def check_out(self):
        return self.perform_check("out")

    # --- helpers ---

    @staticmethod
    def _ip_block_minutes(html):
        """Si el HTML contiene el banner de IP bloqueada, devuelve los minutos
        que indica el server (escalan con reincidencia: 10, 20, ...). Si no
        hay banner, devuelve None."""
        if not html:
            return None
        markers = ("dirección IP", "ha sido bloqueada", "intentos de acceso incorrectos")
        lower = html.lower()
        if sum(1 for m in markers if m.lower() in lower) < 2:
            return None
        m = re.search(r'dentro de\s+(\d+)\s+minutos?', html, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    @classmethod
    def _is_ip_blocked(cls, html):
        return cls._ip_block_minutes(html) is not None

    @staticmethod
    def _extract_login_form(html):
        """Devuelve (token, username_field_name, password_field_name) parseando
        el HTML crudo del login. El form vive dentro de <template
        shadowrootmode="closed"> y los nombres de los campos son aleatorios
        por render."""
        m = re.search(
            r'<form[^>]*class="[^"]*form-login[^"]*"[^>]*>(.*?)</form>',
            html, re.DOTALL,
        )
        if not m:
            raise CheckJCFormError(
                "Login form not found in HTML. CheckJC may have changed the page layout."
            )
        body = m.group(1)

        token_m = re.search(r'name="token"\s+value="([^"]+)"', body)
        user_m = re.search(
            r'class="[^"]*form_username[^"]*"[^>]*?\bname="([^"]+)"', body,
        )
        pass_m = re.search(
            r'class="[^"]*form_password[^"]*"[^>]*?\bname="([^"]+)"', body,
        )
        if not (token_m and user_m and pass_m):
            missing = [k for k, v in (
                ("token", token_m), ("username field", user_m), ("password field", pass_m)
            ) if not v]
            raise CheckJCFormError(
                f"Login form parsed but missing fields: {missing}"
            )
        return token_m.group(1), user_m.group(1), pass_m.group(1)

    @staticmethod
    def _extract_check_form(html):
        """Busca un form .form_check válido en el dashboard y devuelve sus
        campos clave (validator, rnd). Prefiere 'deviceid_self' (el más
        simple: no requiere geo ni QR ni validación de jornada)."""
        preferred = ("deviceid_self", "free_checks", "journey_validator")
        forms = {}
        for fm in re.finditer(
            r'<form[^>]*class="form_check"[^>]*>(.*?)</form>',
            html, re.DOTALL,
        ):
            body = fm.group(1)
            validator_m = re.search(r'name="validator"\s+value="([^"]+)"', body)
            rnd_m = re.search(r'name="rnd"\s+value="(\d+)"', body)
            if validator_m and rnd_m:
                forms[validator_m.group(1)] = {
                    "validator": validator_m.group(1),
                    "rnd": rnd_m.group(1),
                }
        for v in preferred:
            if v in forms:
                return forms[v]
        return next(iter(forms.values()), None)

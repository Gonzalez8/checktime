import logging
import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from checktime.shared.config import get_selenium_timeout, get_simulation_mode

SIMULATION_MODE = get_simulation_mode()

logger = logging.getLogger(__name__)


class CheckJCError(Exception):
    """Base para todos los errores controlados de CheckJC."""


class CheckJCIPBlocked(CheckJCError):
    """CheckJC ha bloqueado el IP por demasiados intentos fallidos.
    Suele liberarse en ~10 minutos."""


class CheckJCLoginRejected(CheckJCError):
    """Login rechazado: el navegador no llegó al dashboard tras el submit.
    Puede ser credenciales malas o rate-limit silencioso."""


class CheckJCSessionLost(CheckJCError):
    """La sesión expiró o el server forzó logout durante el check."""


class CheckJCFormError(CheckJCError):
    """No se pudo localizar el form del login o del dashboard.
    Indica un cambio en el HTML de CheckJC que rompe los selectores."""


class CheckJCUnexpectedResponse(CheckJCError):
    """Respuesta HTTP fuera de lo esperado o navegación a sitio inesperado."""


_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


class CheckJCClient:
    """Cliente para CheckJC v7.4 usando Chromium real vía Playwright.

    Necesario porque CheckJC v7.4 detecta clientes HTTP "ligeros" (urllib,
    curl, curl_cffi, incluso el módulo HTTP de Playwright) y los rechaza
    en silencio, independientemente de IP o headers. La única forma fiable
    es lanzar un navegador real.

    El form de login vive dentro de `<sd-login>` con Declarative Shadow DOM
    closed. Selenium no podía entrar. Playwright tampoco con `page.locator`
    estándar. Solución: usar CDP (DOM.getDocument con pierce=True) para
    localizar los inputs y enviar eventos directos.
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
        self._browser = None
        self._context = None
        self._page = None
        self._cdp = None
        self._timeout_ms = get_selenium_timeout() * 1000

    def __enter__(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation mode enabled for {self.username}")
            return self

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=_CHROME_UA,
            locale="es-ES",
            viewport={"width": 1280, "height": 800},
        )
        self._context.set_default_timeout(self._timeout_ms)
        self._page = self._context.new_page()
        self._cdp = self._context.new_cdp_session(self._page)
        logger.info(f"Chromium iniciado para {self.username}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for closer in (
            getattr(self._context, "close", None),
            getattr(self._browser, "close", None),
            getattr(self._pw, "stop", None),
        ):
            if closer is None:
                continue
            try:
                closer()
            except Exception:
                pass
        if self._browser:
            logger.info(f"Chromium cerrado para {self.username}")

    def login(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation: Login successful for {self.username}")
            return True

        logger.info(f"Navigating to {self.login_url}")
        self._page.goto(self.login_url, wait_until="networkidle")
        # Hidratación de Stencil + render del template shadow DOM closed.
        self._page.wait_for_timeout(2000)

        # Detección temprana de IP bloqueada (banner en /etc/login)
        body_text = self._page.content()
        mins = self._ip_block_minutes(body_text)
        if mins is not None:
            raise CheckJCIPBlocked(
                f"CheckJC blocked this IP for {self.username}. "
                f"Retry available in {mins} minutes (per server)."
            )

        # Buscamos inputs y botón dentro del shadow DOM closed vía CDP.
        user_node, pass_node, btn_node = self._find_login_elements()
        logger.info(
            f"Form found via CDP: user_nodeId={user_node}, "
            f"pass_nodeId={pass_node}, btn_nodeId={btn_node}"
        )

        # Rellenar inputs.
        self._cdp_focus(user_node)
        self._cdp.send("Input.insertText", {"text": self.username})
        self._cdp_focus(pass_node)
        self._cdp.send("Input.insertText", {"text": self.password})

        # Click sobre el botón en sus coordenadas reales (Input.dispatchMouseEvent).
        self._cdp_click(btn_node)
        logger.info(f"Login button clicked for {self.username}")

        # Esperar a que el navegador salga de /login. Si tras N seg seguimos
        # ahí, fue rechazo (el server muestra el form de login otra vez).
        try:
            self._page.wait_for_url(
                lambda url: "/login" not in url, timeout=15000
            )
        except PWTimeout:
            # ¿Llegó banner de IP bloqueada tras el intento?
            mins = self._ip_block_minutes(self._page.content())
            if mins is not None:
                raise CheckJCIPBlocked(
                    f"CheckJC blocked this IP after failed attempts for {self.username}. "
                    f"Retry available in {mins} minutes (per server)."
                )
            raise CheckJCLoginRejected(
                f"CheckJC rejected the login for {self.username}: "
                f"still at {self._page.url!r} after submit. "
                f"Check if the user can log in via the web."
            )

        logger.info(f"Login successful for {self.username}, landed at {self._page.url}")
        return True

    def perform_check(self, check_type: str):
        """Realiza un fichaje (entrada o salida).

        CheckJC v7.4 no distingue 'in' / 'out' en el click: registra un
        check en el momento, el server decide qué es. El parámetro se
        mantiene para compatibilidad con la interfaz anterior y logging.
        """
        if SIMULATION_MODE:
            logger.info(f"Simulation: Check {check_type} completed for {self.username}")
            return True

        # Después del login el navegador suele estar ya en /portal/employee.
        if "/portal/employee" not in self._page.url:
            logger.info(f"Navigating to {self.portal_url}")
            self._page.goto(self.portal_url, wait_until="domcontentloaded")

        if "/login" in self._page.url:
            raise CheckJCSessionLost(
                f"Lost session before submitting check {check_type} for {self.username} "
                f"(redirected to login)."
            )

        # El boton #btn-check vive en light DOM pero esta oculto (clase
        # `hidden-soft`) hasta que el AJAX a /rest/portal/employee/liveData.json
        # responde con `portal_host` y el JS hace .show(). Esperamos a que sea
        # interactuable; si no llega, capturamos contexto para diagnosticar.
        try:
            self._page.wait_for_selector("#btn-check", state="visible", timeout=15000)
        except PWTimeout:
            diag = self._page.evaluate(
                "() => ({"
                "url: location.href,"
                "btnExists: !!document.querySelector('#btn-check'),"
                "btnHidden: (function(){"
                "  const e=document.querySelector('#btn-check');"
                "  if(!e) return null;"
                "  return {display: getComputedStyle(e).display, class: e.className,"
                "    parentClass: e.parentElement ? e.parentElement.className : ''};"
                "})()"
                "})"
            )
            raise CheckJCFormError(
                f"#btn-check did not become visible on dashboard for {self.username} "
                f"within 15s. Diagnostics: {diag}. "
                f"Possible cause: the user has no portal_host configured in CheckJC."
            )

        logger.info(f"Submitting check ({check_type}) for {self.username}")
        # Click vía Playwright (selectores normales bastan: #btn-check NO esta
        # en shadow DOM, solo el login). El handler JS de CheckJC decide el
        # flow: para deviceid_self sin confirmacion de ubicacion hace submit
        # automatico del form interno; en otros casos abre un modal.
        self._page.click("#btn-check")

        # Esperar a que la UI reaccione: recarga o actualiza el listado.
        self._page.wait_for_timeout(3000)

        if "/login" in self._page.url or "/logout" in self._page.url:
            raise CheckJCSessionLost(
                f"Session dropped after check {check_type} for {self.username} "
                f"(at {self._page.url!r})."
            )

        logger.info(
            f"Check {check_type} submitted for {self.username} (at {self._page.url})"
        )
        return True

    def check_in(self):
        return self.perform_check("in")

    def check_out(self):
        return self.perform_check("out")

    # --- helpers ---

    def _cdp_focus(self, node_id):
        self._cdp.send("DOM.focus", {"nodeId": node_id})

    def _cdp_click(self, node_id):
        """Envía un click real (mousePressed + mouseReleased) en el centro
        del box del nodo. Funciona aunque el nodo viva dentro de un shadow
        root closed: las coordenadas son globales."""
        box = self._cdp.send("DOM.getBoxModel", {"nodeId": node_id})
        c = box["model"]["content"]
        x = (c[0] + c[2]) / 2
        y = (c[1] + c[5]) / 2
        for event_type in ("mousePressed", "mouseReleased"):
            self._cdp.send("Input.dispatchMouseEvent", {
                "type": event_type, "x": x, "y": y,
                "button": "left", "clickCount": 1,
            })

    def _find_login_elements(self):
        """Recorre el DOM (incluido shadow DOM closed via pierce=True) y
        devuelve los nodeIds del primer username/password/btn-login visibles."""
        dom = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        user_nodes = []
        pass_nodes = []
        btn_nodes = []

        def walk(node):
            name = node.get("nodeName", "").lower()
            attrs = self._attrs(node)
            if name == "input":
                cls = attrs.get("class", "")
                if "form_username" in cls:
                    user_nodes.append(node["nodeId"])
                elif "form_password" in cls:
                    pass_nodes.append(node["nodeId"])
            elif name == "button" and attrs.get("id") == "btn-login":
                btn_nodes.append(node["nodeId"])
            for child in (node.get("children") or []):
                walk(child)
            for child in (node.get("shadowRoots") or []):
                walk(child)
            if node.get("contentDocument"):
                walk(node["contentDocument"])

        walk(dom["root"])
        user = self._first_visible(user_nodes)
        pwd = self._first_visible(pass_nodes)
        btn = self._first_visible(btn_nodes)
        if not (user and pwd and btn):
            # Capturamos info útil para distinguir "CheckJC cambió HTML" de
            # "CheckJC nos sirve HTML lite porque tiene la IP marcada".
            try:
                body_size = len(self._page.content() or "")
                screenshot_path = f"/var/log/checktime/checkjc_failed_login_{self.username}.png"
                self._page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                body_size = -1
                screenshot_path = "(screenshot failed)"
            raise CheckJCFormError(
                f"Login form elements not found in DOM for {self.username}. "
                f"Counts: usernames={len(user_nodes)}, passwords={len(pass_nodes)}, "
                f"buttons={len(btn_nodes)}. Visible: "
                f"user={bool(user)}, pwd={bool(pwd)}, btn={bool(btn)}. "
                f"Page body size: {body_size} bytes (normal is ~70KB; if much smaller "
                f"the server is serving a 'lite' variant because the egress IP is marked). "
                f"Screenshot: {screenshot_path}"
            )
        return user, pwd, btn

    def _find_check_button(self):
        dom = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        candidates = []

        def walk(node):
            attrs = self._attrs(node)
            if attrs.get("id") == "btn-check":
                candidates.append(node["nodeId"])
            for child in (node.get("children") or []):
                walk(child)
            for child in (node.get("shadowRoots") or []):
                walk(child)
            if node.get("contentDocument"):
                walk(node["contentDocument"])

        walk(dom["root"])
        return self._first_visible(candidates)

    def _first_visible(self, node_ids):
        for nid in node_ids:
            try:
                box = self._cdp.send("DOM.getBoxModel", {"nodeId": nid})
                c = box["model"]["content"]
                if abs(c[2] - c[0]) > 0 and abs(c[5] - c[1]) > 0:
                    return nid
            except Exception:
                continue
        return None

    @staticmethod
    def _attrs(node):
        out = {}
        a = node.get("attributes") or []
        for i in range(0, len(a), 2):
            out[a[i]] = a[i + 1]
        return out

    @staticmethod
    def _ip_block_minutes(html):
        """Si el HTML contiene el banner de IP bloqueada, devuelve los minutos
        que indica el server. Si no hay banner, devuelve None."""
        if not html:
            return None
        markers = ("dirección IP", "ha sido bloqueada", "intentos de acceso incorrectos")
        lower = html.lower()
        if sum(1 for m in markers if m.lower() in lower) < 2:
            return None
        m = re.search(r'dentro de\s+(\d+)\s+minutos?', html, re.IGNORECASE)
        return int(m.group(1)) if m else 0

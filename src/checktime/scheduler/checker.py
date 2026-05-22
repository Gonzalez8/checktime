import base64
import logging
import re
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from checktime.shared.config import (
    get_checkjc_lite_retries,
    get_checkjc_lite_retry_seconds,
    get_selenium_timeout,
    get_simulation_mode,
)

# Body sizes below this are treated as the CheckJC "lite" anti-bot variant.
# Normal /login renders ~70 KB; lite is consistently <10 KB (we've seen
# ~7.7-8 KB in production). 20 KB is a safe threshold.
_LITE_BODY_THRESHOLD = 20000

SIMULATION_MODE = get_simulation_mode()

logger = logging.getLogger(__name__)


class CheckJCError(Exception):
    """Base para todos los errores controlados de CheckJC."""


class CheckJCIPBlocked(CheckJCError):
    """CheckJC ha bloqueado el IP por demasiados intentos fallidos.
    Suele liberarse en ~10 minutos."""


class CheckJCAccountLocked(CheckJCError):
    """CheckJC ha bloqueado la CUENTA del usuario (no el IP) por
    demasiados intentos fallidos. Esto NO se libera con tiempo corto
    ni cambiando IP — solo el supervisor/admin de CheckJC puede
    desbloquearlo. Cuando ocurre debemos detener el scheduler para
    ese usuario y avisar inmediatamente, no reintentar."""


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


class CheckJCCaptchaFailed(CheckJCError):
    """No se pudo resolver el captcha de /verification.

    Razones típicas: el usuario no respondió a tiempo por Telegram, el
    solver devolvió None, o respondió pero el captcha era incorrecto en
    los dos intentos permitidos.
    """


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

    def __init__(self, username, password, subdomain,
                 captcha_solver=None, user=None, check_type: str = "in"):
        if not username or not password or not subdomain:
            raise ValueError("CheckJC username, password, and subdomain must be provided.")

        self.username = username
        self.password = password
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.checkjc.com"
        self.login_url = f"{self.base_url}/login"
        self.portal_url = f"{self.base_url}/portal/employee"
        self.verification_url = f"{self.base_url}/portal/employee/verification"

        # Captcha-relay dependencies. Optional so unit tests / simulation
        # don't need to wire them up.
        self._captcha_solver = captcha_solver
        self._user = user
        self._check_type = check_type

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

        max_attempts = get_checkjc_lite_retries() + 1
        retry_wait_ms = get_checkjc_lite_retry_seconds() * 1000

        user_node = pass_node = btn_node = None
        last_body_size = None
        for attempt in range(1, max_attempts + 1):
            logger.info(
                f"Navigating to {self.login_url} (attempt {attempt}/{max_attempts})"
            )
            self._page.goto(self.login_url, wait_until="networkidle")
            # Hidratación de Stencil + render del template shadow DOM closed.
            self._page.wait_for_timeout(2000)

            body_text = self._page.content()
            body_size = len(body_text or "")
            last_body_size = body_size

            # Per-user account lockout — completely fatal until a human
            # at CheckJC unblocks. Detect FIRST so we never retry past
            # this point and risk extending the ban.
            remaining = self._account_lock_message(body_text)
            if remaining is not None:
                raise CheckJCAccountLocked(
                    f"CheckJC account for {self.username} is locked. "
                    f"Remaining: {remaining}. The user must ask their "
                    f"CheckJC supervisor or admin to unlock the account. "
                    f"Disable auto-checkin for this user in CheckTime to "
                    f"stop the scheduler from making things worse."
                )

            # Banner de IP bloqueada — esto no se arregla reintentando.
            mins = self._ip_block_minutes(body_text)
            if mins is not None:
                raise CheckJCIPBlocked(
                    f"CheckJC blocked this IP for {self.username}. "
                    f"Retry available in {mins} minutes (per server)."
                )

            # Intentamos siempre encontrar el form, sin importar el tamaño:
            # hemos visto bodys de 7-8 KB donde Stencil sí estaba hidratado
            # (caché JS de intentos previos en el mismo Context).
            try:
                user_node, pass_node, btn_node = self._find_login_elements()
                if body_size < _LITE_BODY_THRESHOLD:
                    logger.info(
                        "Form usable despite small body (%d bytes) for %s "
                        "— probably hydrated from cache",
                        body_size, self.username,
                    )
                break
            except CheckJCFormError:
                # Body pequeño + form no encontrado = anti-bot lite real.
                # Retry; el goto siguiente reutiliza el mismo Context, así
                # que caché y cookies persisten.
                if body_size < _LITE_BODY_THRESHOLD and attempt < max_attempts:
                    logger.warning(
                        "Lite variant for %s (body=%d bytes, attempt %d/%d); "
                        "sleeping %ds before retry",
                        self.username, body_size, attempt, max_attempts,
                        retry_wait_ms // 1000,
                    )
                    self._page.wait_for_timeout(retry_wait_ms)
                    continue
                # Body normal pero form no encontrado: cambio de DOM real,
                # no se arregla esperando. Propagar tal cual.
                raise

        if user_node is None or pass_node is None or btn_node is None:
            # Defensive: salimos del bucle sin éxito ni excepción.
            raise CheckJCFormError(
                f"Login attempts exhausted for {self.username} "
                f"(last body size: {last_body_size} bytes). "
                f"Consider rotating the NordVPN exit IP or raising "
                f"CHECKJC_LITE_RETRY_SECONDS."
            )

        logger.info(
            f"Form found via CDP: user_nodeId={user_node}, "
            f"pass_nodeId={pass_node}, btn_nodeId={btn_node}"
        )

        # Stencil sometimes hydrates the form's hidden CSRF token *after*
        # the visible inputs become interactable. On a small body (lite
        # variant) we wait extra before clicking to give it time. We do
        # NOT retry on rejection — each failed submit counts toward
        # CheckJC's per-account lockout, and the v1.9.4 double-submit
        # caused a real account ban. The pre-`login()` lite-variant
        # retry loop already handled DOM hydration; this just adds a
        # safety wait for the CSRF token specifically.
        if last_body_size is not None and last_body_size < _LITE_BODY_THRESHOLD:
            logger.info(
                "Body is small (%d bytes); waiting 3s extra for Stencil to "
                "hydrate the form token before submitting",
                last_body_size,
            )
            self._page.wait_for_timeout(3000)

        # Rellenar inputs.
        self._cdp_focus(user_node)
        self._cdp.send("Input.insertText", {"text": self.username})
        self._cdp_focus(pass_node)
        self._cdp.send("Input.insertText", {"text": self.password})

        # Click sobre el botón en sus coordenadas reales.
        self._cdp_click(btn_node)
        logger.info("Login button clicked for %s", self.username)

        # Esperar a que el navegador salga de /login. Si tras N seg
        # seguimos ahí, fue rechazo. NO reintentamos: cuenta puede
        # bloquearse permanentemente tras X fallos consecutivos.
        try:
            self._page.wait_for_url(
                lambda url: "/login" not in url, timeout=15000
            )
        except PWTimeout:
            # Check both new banners that the retry could have surfaced:
            body_after = self._page.content()
            remaining = self._account_lock_message(body_after)
            if remaining is not None:
                raise CheckJCAccountLocked(
                    f"CheckJC locked the account for {self.username} after "
                    f"this submit. Remaining: {remaining}. Disable "
                    f"auto-checkin for this user in CheckTime."
                )
            mins = self._ip_block_minutes(body_after)
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

        # CheckJC may now serve /portal/employee/verification — a 6-digit
        # captcha gate added after v7.4. If we end up there, hand it off to
        # the captcha solver (Telegram human today, LLM tomorrow).
        if "/verification" in self._page.url:
            self._solve_verification()

        return True

    def _solve_verification(self):
        """Handle CheckJC's post-login captcha page.

        Strategy (validated end-to-end against production CheckJC):
        - The 10 keypad buttons each carry a data-value letter that stays
          stable for the session; only positions shuffle after each click.
        - Capture the captcha image and the 10 keypad button images, hand
          everything to the solver. The solver (Telegram human today,
          LLM tomorrow) is responsible for reading BOTH the distorted
          captcha and the 10 clean keypad digits and returning the
          6-letter click sequence.
        - For each letter, re-read the DOM and click its current
          position. Positions reshuffle after each click but the letters
          themselves are stable.
        - Submit, verify we landed on /portal/employee. Retry once on
          /verification reappearing (wrong reply).
        """
        if self._captcha_solver is None or self._user is None:
            raise CheckJCCaptchaFailed(
                f"CheckJC served /verification for {self.username} but no "
                f"captcha solver was configured. Check scheduler wiring."
            )

        max_captcha_attempts = 2
        for attempt in range(1, max_captcha_attempts + 1):
            captcha_bytes = self._capture_captcha_image()
            keypad_buttons = self._capture_keypad_buttons()
            if not captcha_bytes or len(keypad_buttons) < 10:
                raise CheckJCFormError(
                    f"Could not extract captcha image / keypad buttons "
                    f"for {self.username} on attempt {attempt}. "
                    f"CheckJC probably changed the verification page HTML."
                )

            # The solver wants (letter, png_bytes). Keep order stable across
            # the call so the solver and our DOM agree on which button is
            # at which index.
            keypad_for_solver = [(letter, png) for letter, _, _, png in keypad_buttons]

            sequence = self._captcha_solver.solve(
                captcha_image_bytes=captcha_bytes,
                keypad=keypad_for_solver,
                user=self._user,
                check_type=self._check_type,
                attempt=attempt,
            )
            if not sequence:
                raise CheckJCCaptchaFailed(
                    f"Captcha solver returned no sequence for {self.username} "
                    f"on attempt {attempt}. Likely user timeout or malformed reply."
                )
            if len(sequence) != 6:
                logger.warning(
                    "Captcha solver returned %d letters (expected 6) for %s",
                    len(sequence), self.username,
                )
                if attempt < max_captcha_attempts:
                    continue
                raise CheckJCCaptchaFailed(
                    f"Captcha solver returned wrong-length sequence {sequence!r} "
                    f"for {self.username}."
                )

            logger.info(
                "Submitting captcha for %s (attempt %d): letters %s",
                self.username, attempt, sequence,
            )
            for letter in sequence:
                pos = self._current_position_of_letter(letter)
                if pos is None:
                    raise CheckJCFormError(
                        f"Letter {letter!r} disappeared from keypad mid-click "
                        f"for {self.username}"
                    )
                self._cdp_click_at(pos)

            submit_pos = self._current_submit_position()
            if submit_pos is None:
                raise CheckJCFormError(
                    f"Submit button not found on verification page for {self.username}"
                )
            self._cdp_click_at(submit_pos)

            # Wait for navigation away from /verification
            try:
                self._page.wait_for_url(
                    lambda url: "/verification" not in url,
                    timeout=10000,
                )
            except PWTimeout:
                pass

            if "/portal/employee" in self._page.url and "/verification" not in self._page.url:
                logger.info(
                    "Captcha cleared for %s on attempt %d, landed at %s",
                    self.username, attempt, self._page.url,
                )
                return

            if "/login" in self._page.url:
                raise CheckJCSessionLost(
                    f"Lost session after captcha submit for {self.username} "
                    f"(redirected back to /login)."
                )

            # Still on /verification: wrong digits. Retry with a new captcha.
            logger.warning(
                "Captcha submit didn't clear for %s on attempt %d (url=%s); retrying",
                self.username, attempt, self._page.url,
            )

        raise CheckJCCaptchaFailed(
            f"Captcha verification failed for {self.username} after "
            f"{max_captcha_attempts} attempts."
        )

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
                # Solo viewport (1280x800): suficiente para diagnosticar y
                # mucho más ligero que full_page (~150 KB vs 1-2 MB).
                self._page.screenshot(path=screenshot_path, full_page=False)
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

    # --- captcha helpers ---

    def _cdp_click_at(self, pos):
        x, y = pos
        for event_type in ("mousePressed", "mouseReleased"):
            self._cdp.send("Input.dispatchMouseEvent", {
                "type": event_type, "x": x, "y": y,
                "button": "left", "clickCount": 1,
            })
        # Small breather: gives CheckJC's JS time to re-shuffle the keypad
        # before we ask for the next click's coordinates.
        self._page.wait_for_timeout(120)

    def _capture_captcha_image(self) -> Optional[bytes]:
        """Return the JPEG bytes of the distorted captcha image, or None."""
        dom = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        images = []

        def walk(node):
            name = (node.get("nodeName") or "").lower()
            attrs = self._attrs(node)
            if name == "img":
                src = attrs.get("src", "")
                if src.startswith("data:image/jpeg;base64,") or (
                    src.startswith("data:image") and len(src) > 5000
                ):
                    images.append(src)
            for child in (node.get("children") or []):
                walk(child)
            for child in (node.get("shadowRoots") or []):
                walk(child)
            if node.get("contentDocument"):
                walk(node["contentDocument"])

        walk(dom["root"])
        if not images:
            return None
        # Captcha is the largest data:image; the rest are tiny keypad PNGs
        images.sort(key=len, reverse=True)
        src = images[0]
        try:
            _, b64 = src.split(",", 1)
            return base64.b64decode(b64)
        except Exception as e:
            logger.error("Failed to decode captcha image: %s", e)
            return None

    def _capture_keypad_buttons(self):
        """Return list of (letter, nodeId, (cx,cy), png_bytes) for each
        keypad shuffle-button, or empty list on failure.

        The PNG bytes are the image embedded inside each button — used by
        the keypad OCR to map letter -> digit.
        """
        dom = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        out = []

        def find_inner_img_src(node):
            name = (node.get("nodeName") or "").lower()
            attrs = self._attrs(node)
            if name == "img" and attrs.get("src", "").startswith("data:image"):
                return attrs["src"]
            for child in (node.get("children") or []):
                r = find_inner_img_src(child)
                if r:
                    return r
            for child in (node.get("shadowRoots") or []):
                r = find_inner_img_src(child)
                if r:
                    return r
            return None

        def walk(node):
            name = (node.get("nodeName") or "").lower()
            attrs = self._attrs(node)
            if name == "button":
                cls = attrs.get("class", "")
                letter = attrs.get("data-value")
                if "btn-shuffle" in cls and letter:
                    try:
                        box = self._cdp.send("DOM.getBoxModel", {"nodeId": node["nodeId"]})
                        c = box["model"]["content"]
                        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[5]) / 2
                    except Exception:
                        return
                    img_src = find_inner_img_src(node)
                    if not img_src:
                        return
                    try:
                        _, b64 = img_src.split(",", 1)
                        png_bytes = base64.b64decode(b64)
                    except Exception:
                        return
                    out.append((letter, node["nodeId"], (cx, cy), png_bytes))
            for child in (node.get("children") or []):
                walk(child)
            for child in (node.get("shadowRoots") or []):
                walk(child)
            if node.get("contentDocument"):
                walk(node["contentDocument"])

        walk(dom["root"])
        return out

    def _current_position_of_letter(self, letter: str):
        """Re-read the DOM and return the current (cx, cy) of `letter`, or None."""
        dom = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        result = []

        def walk(node):
            name = (node.get("nodeName") or "").lower()
            attrs = self._attrs(node)
            if name == "button" and attrs.get("data-value") == letter and "btn-shuffle" in attrs.get("class", ""):
                try:
                    box = self._cdp.send("DOM.getBoxModel", {"nodeId": node["nodeId"]})
                    c = box["model"]["content"]
                    result.append(((c[0] + c[2]) / 2, (c[1] + c[5]) / 2))
                except Exception:
                    pass
            for child in (node.get("children") or []):
                walk(child)
            for child in (node.get("shadowRoots") or []):
                walk(child)
            if node.get("contentDocument"):
                walk(node["contentDocument"])

        walk(dom["root"])
        return result[0] if result else None

    def _current_submit_position(self):
        dom = self._cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
        result = []

        def walk(node):
            name = (node.get("nodeName") or "").lower()
            attrs = self._attrs(node)
            if name == "button" and "btn-success" in attrs.get("class", ""):
                try:
                    box = self._cdp.send("DOM.getBoxModel", {"nodeId": node["nodeId"]})
                    c = box["model"]["content"]
                    result.append(((c[0] + c[2]) / 2, (c[1] + c[5]) / 2))
                except Exception:
                    pass
            for child in (node.get("children") or []):
                walk(child)
            for child in (node.get("shadowRoots") or []):
                walk(child)
            if node.get("contentDocument"):
                walk(node["contentDocument"])

        walk(dom["root"])
        return result[0] if result else None

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

    @staticmethod
    def _account_lock_message(html):
        """Detect CheckJC's per-user account lockout banner.

        Sample text (May 2026):
            "No se permitirán nuevos intentos de acceso para el usuario
             47779708z hasta dentro de 2 meses, 30 días, 23 horas, 17
             minutos. Contacte con su supervisor o administrador de la
             plataforma."

        Returns the human-readable remaining time ("2 meses, 30 días,
        23 horas, 17 minutos") if the banner is present, else None.
        Catching this early lets us short-circuit before submitting
        another doomed login attempt.
        """
        if not html:
            return None
        if "no se permitirán nuevos intentos" not in html.lower():
            return None
        m = re.search(
            r"hasta dentro de\s+([^.]+?)\.\s*Contacte",
            html, re.IGNORECASE,
        )
        return m.group(1).strip() if m else "unknown duration"

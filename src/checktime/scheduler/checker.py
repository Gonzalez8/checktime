import base64
import logging
import random
import re
from typing import Optional
# rebrowser-playwright is a patched drop-in but, on PyPI/Python, it ships
# under the `rebrowser_playwright` module name (NOT `playwright`). Prefer it
# when present (it removes the Runtime.enable CDP leak), and fall back to
# stock playwright so local dev / tests without the fork still work.
try:
    from rebrowser_playwright.sync_api import (
        sync_playwright, TimeoutError as PWTimeout,
    )
except ModuleNotFoundError:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from checktime.shared.config import (
    get_captcha_click_delay_max_ms,
    get_captcha_click_delay_min_ms,
    get_captcha_read_delay_max_ms,
    get_captcha_read_delay_min_ms,
    get_captcha_submit_delay_max_ms,
    get_captcha_submit_delay_min_ms,
    get_checkjc_lite_retries,
    get_checkjc_lite_retry_seconds,
    get_keystroke_delay_max_ms,
    get_keystroke_delay_min_ms,
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


# Chrome major used to keep UA, Sec-CH-UA client hints and navigator
# .userAgentData all in lock-step. InfoJC's report (28/05/2026) flagged
# the literal "HeadlessChrome/135" token; the fix is two-fold:
#   1) run Chromium in the *new* headless mode (no "HeadlessChrome" token
#      in the UA or client hints), and
#   2) present a fingerprint that is INTERNALLY COHERENT with the real
#      host. The container is Linux x86_64, so we advertise a normal Linux
#      desktop Chrome. Faking macOS on a Linux box would leave the real
#      platform leaking through WebGL/navigator.platform — a mismatch that
#      is itself a bot tell. A standard Linux Chrome is a perfectly common,
#      non-blacklisted client.
#
# The value MUST match the Chromium that rebrowser-playwright actually
# bundles (1.52.0 -> Chromium 136). Declaring a version newer than the real
# engine is itself a detectable mismatch (feature probing, JS quirks), so we
# keep UA / Sec-CH-UA / userAgentData in lock-step with the running engine.
# Fallback only. The REAL value is read from the launched engine
# (browser.version) at runtime, so UA/Sec-CH-UA/userAgentData always match
# the Chromium that rebrowser-playwright actually ships — declaring a version
# different from the running engine is itself a detectable mismatch.
_CHROME_MAJOR = "136"
_SEC_CH_UA_PLATFORM = '"Linux"'

# Injected before any page script runs. Patches the most common headless
# tells (navigator.webdriver, missing chrome object, plugins/languages
# inconsistencies) that anti-bot stacks check for. Belt-and-braces on top
# of --disable-blink-features=AutomationControlled and --headless=new,
# which alone leave a couple of these gaps depending on the Chromium build.
#
# __MAJOR__ is substituted per-session (from the real engine version) so
# navigator.userAgentData stays in lock-step with the UA / Sec-CH-UA.
# Everything here describes a normal Linux desktop Chrome — coherent with the
# real host, no macOS mismatch.
_STEALTH_INIT_SCRIPT_TEMPLATE = """
(() => {
  // ----------------------------------------------------------------------
  // toString leak guard. Anti-bot code often inspects our spoofs via
  // `fn.toString()` (or `Object.getOwnPropertyDescriptor(navigator,'x').get
  // .toString()`). A native getter prints "function get x() { [native code]
  // }"; our arrow/closure prints its source, which is a dead giveaway.
  // We proxy Function.prototype.toString so any function we register reports
  // a native-looking string. Register a spoof with markNative(fn, 'name').
  // ----------------------------------------------------------------------
  const _spoofed = new WeakMap();
  const _origToString = Function.prototype.toString;
  const markNative = (fn, name) => {
    try {
      _spoofed.set(fn, 'function ' + (name || fn.name || '') +
        '() { [native code] }');
    } catch (_) {}
    return fn;
  };
  try {
    const proxyToString = new Proxy(_origToString, {
      apply(target, thisArg, args) {
        if (_spoofed.has(thisArg)) return _spoofed.get(thisArg);
        return Reflect.apply(target, thisArg, args);
      },
    });
    // The proxy must also report native for ITS OWN toString.
    _spoofed.set(proxyToString, 'function toString() { [native code] }');
    Function.prototype.toString = proxyToString;
  } catch (_) {}

  // Helper: define a property with a getter that itself reports native code.
  const defineNativeGetter = (obj, prop, getter, name) => {
    try {
      markNative(getter, name || ('get ' + prop));
      Object.defineProperty(obj, prop, { get: getter, configurable: true });
    } catch (_) {}
  };

  // navigator.webdriver: a REAL Chrome returns `false`, not `undefined`.
  // Returning undefined (old stealth advice) is itself anomalous; force the
  // human value `false`.
  try {
    if (navigator.webdriver !== false) {
      defineNativeGetter(navigator, 'webdriver', () => false, 'get webdriver');
    }
  } catch (_) {}

  defineNativeGetter(navigator, 'languages',
    () => ['es-ES', 'es', 'en-US', 'en'], 'get languages');

  // navigator.platform / vendor / hardware: must be coherent with a Linux
  // x86_64 desktop Chrome (matches the UA). The old plugins=[1,2,3,4,5] was
  // a tell (no real Chrome returns bare integers) — build a realistic
  // PluginArray of the 5 PDF entries modern Chrome exposes instead.
  defineNativeGetter(navigator, 'platform', () => 'Linux x86_64', 'get platform');
  defineNativeGetter(navigator, 'vendor', () => 'Google Inc.', 'get vendor');
  defineNativeGetter(navigator, 'hardwareConcurrency', () => 8,
    'get hardwareConcurrency');
  defineNativeGetter(navigator, 'deviceMemory', () => 8, 'get deviceMemory');
  defineNativeGetter(navigator, 'maxTouchPoints', () => 0, 'get maxTouchPoints');

  // Realistic plugins / mimeTypes. Modern Chrome ships 5 PDF "plugins" all
  // backed by the internal PDF viewer. Shape them like real Plugin objects.
  try {
    const pdfNames = [
      'PDF Viewer', 'Chrome PDF Viewer', 'Chromium PDF Viewer',
      'Microsoft Edge PDF Viewer', 'WebKit built-in PDF',
    ];
    const mimeA = { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' };
    const mimeB = { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' };
    const plugins = pdfNames.map((n) => ({
      name: n, filename: 'internal-pdf-viewer',
      description: 'Portable Document Format', length: 2,
      0: mimeA, 1: mimeB,
      item() { return mimeA; }, namedItem() { return mimeA; },
    }));
    plugins.item = function (i) { return this[i] || null; };
    plugins.namedItem = function (n) {
      return this.find((p) => p.name === n) || null;
    };
    plugins.refresh = function () {};
    defineNativeGetter(navigator, 'plugins', () => plugins, 'get plugins');
    const mimeTypes = [mimeA, mimeB];
    mimeTypes.item = function (i) { return this[i] || null; };
    mimeTypes.namedItem = function (t) {
      return this.find((m) => m.type === t) || null;
    };
    defineNativeGetter(navigator, 'mimeTypes', () => mimeTypes, 'get mimeTypes');
  } catch (_) {}

  // NetworkInformation (navigator.connection). Headless may omit it.
  try {
    if (!navigator.connection) {
      defineNativeGetter(navigator, 'connection', () => ({
        effectiveType: '4g', rtt: 50, downlink: 10, saveData: false,
        onchange: null,
      }), 'get connection');
    }
  } catch (_) {}

  // window.chrome: a real Chrome exposes app/runtime/csi/loadTimes. The bare
  // {runtime:{}} we had before is itself suspicious. Provide a fuller shape.
  try {
    if (!window.chrome || !window.chrome.runtime) {
      window.chrome = window.chrome || {};
      window.chrome.runtime = window.chrome.runtime || {
        connect: function () {}, sendMessage: function () {},
        onMessage: { addListener: function () {} },
      };
      window.chrome.app = window.chrome.app || {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
      };
      window.chrome.csi = window.chrome.csi || function () {
        return { startE: Date.now(), onloadT: Date.now(), pageT: 1, tran: 15 };
      };
      window.chrome.loadTimes = window.chrome.loadTimes || function () {
        return {
          requestTime: Date.now() / 1000, startLoadTime: Date.now() / 1000,
          commitLoadTime: Date.now() / 1000, finishLoadTime: Date.now() / 1000,
          firstPaintTime: Date.now() / 1000, navigationType: 'Other',
          wasFetchedViaSpdy: true, wasNpnNegotiated: true, npnNegotiatedProtocol: 'h2',
          wasAlternateProtocolAvailable: false, connectionInfo: 'h2',
        };
      };
      markNative(window.chrome.csi, 'csi');
      markNative(window.chrome.loadTimes, 'loadTimes');
    }
  } catch (_) {}

  // screen / window outer dims: headless commonly reports outerWidth/Height
  // as 0 and a screen that contradicts the viewport. Make them coherent with
  // the inner viewport (a maximized desktop window).
  try {
    const iw = window.innerWidth || 1280;
    const ih = window.innerHeight || 800;
    if (!window.outerWidth)  Object.defineProperty(window, 'outerWidth',  { get: () => iw, configurable: true });
    if (!window.outerHeight) Object.defineProperty(window, 'outerHeight', { get: () => ih + 74, configurable: true });
    const sw = Math.max(iw, 1280);
    const sh = Math.max(ih + 74, 800);
    defineNativeGetter(screen, 'width', () => sw, 'get width');
    defineNativeGetter(screen, 'height', () => sh, 'get height');
    defineNativeGetter(screen, 'availWidth', () => sw, 'get availWidth');
    defineNativeGetter(screen, 'availHeight', () => sh - 27, 'get availHeight');
    defineNativeGetter(screen, 'colorDepth', () => 24, 'get colorDepth');
    defineNativeGetter(screen, 'pixelDepth', () => 24, 'get pixelDepth');
  } catch (_) {}

  // userAgentData: in legacy headless this leaks a "HeadlessChrome" brand.
  // Pin it to a normal Chrome on Linux so the high-entropy hints CheckJC
  // can request never reveal automation, and match _CHROME_UA exactly.
  try {
    const brands = [
      { brand: 'Chromium', version: '__MAJOR__' },
      { brand: 'Google Chrome', version: '__MAJOR__' },
      { brand: 'Not_A Brand', version: '24' },
    ];
    const getHEV = (hints) => Promise.resolve({
      architecture: 'x86',
      bitness: '64',
      brands: brands,
      fullVersionList: brands.map(b => ({
        brand: b.brand,
        version: b.brand === 'Not_A Brand' ? '24.0.0.0' : '__MAJOR__.0.0.0',
      })),
      mobile: false,
      model: '',
      platform: 'Linux',
      platformVersion: '6.6.0',
      uaFullVersion: '__MAJOR__.0.0.0',
      wow64: false,
    });
    markNative(getHEV, 'getHighEntropyValues');
    const uaData = {
      brands: brands,
      mobile: false,
      platform: 'Linux',
      getHighEntropyValues: getHEV,
      toJSON: function () { return this; },
    };
    defineNativeGetter(navigator, 'userAgentData', () => uaData, 'get userAgentData');
  } catch (_) {}

  // WebGL vendor/renderer: software headless reports "SwiftShader", a clear
  // automation tell. Report a plausible Linux ANGLE/Mesa GPU instead.
  try {
    const spoof = (proto) => {
      if (!proto) return;
      const orig = proto.getParameter;
      const patched = function (p) {
        if (p === 37445) return 'Google Inc. (Intel)';            // UNMASKED_VENDOR_WEBGL
        if (p === 37446) {                                         // UNMASKED_RENDERER_WEBGL
          return 'ANGLE (Intel, Mesa Intel(R) UHD Graphics (CML GT2), OpenGL 4.6)';
        }
        return orig.call(this, p);
      };
      markNative(patched, 'getParameter');
      proto.getParameter = patched;
    };
    spoof(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
    spoof(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
  } catch (_) {}

  try {
    const origQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (origQuery) {
      const patchedQuery = (params) =>
        params && params.name === 'notifications'
          ? Promise.resolve({ state: Notification.permission })
          : origQuery(params);
      markNative(patchedQuery, 'query');
      window.navigator.permissions.query = patchedQuery;
    }
  } catch (_) {}
})();
"""


def _fingerprint_for_major(major: str):
    """Build (user_agent, sec_ch_ua, stealth_script) for a Chrome major so the
    UA string, Sec-CH-UA client hints and navigator.userAgentData all match
    the real engine version that is actually running."""
    ua = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
    )
    sec_ch_ua = (
        f'"Chromium";v="{major}", '
        f'"Google Chrome";v="{major}", '
        '"Not_A Brand";v="24"'
    )
    script = _STEALTH_INIT_SCRIPT_TEMPLATE.replace("__MAJOR__", major)
    return ua, sec_ch_ua, script


# Module-level defaults, used if the engine version can't be read at runtime.
_CHROME_UA, _SEC_CH_UA, _STEALTH_INIT_SCRIPT = _fingerprint_for_major(_CHROME_MAJOR)


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

        # Diagnostic ring buffers — populated by the listeners installed in
        # __enter__ so that when a login is rejected we can see exactly what
        # CheckJC returned over the wire (status, JSON body of the auth XHR),
        # what the page logged to console, and any uncaught JS errors. This
        # is the missing piece when credentials are valid via the web but
        # the bot is silently bounced back to /login. All are capped so a
        # long-lived context can't grow memory unbounded.
        # Fingerprint actually used this session. Rebuilt in __enter__ from
        # the real engine version so UA/Sec-CH-UA/userAgentData never lie
        # about the Chromium that's running. Module defaults until then.
        self._chrome_ua = _CHROME_UA
        self._sec_ch_ua = _SEC_CH_UA
        self._stealth_script = _STEALTH_INIT_SCRIPT
        self._net_events = []
        self._console_events = []
        self._page_errors = []
        # Requests actually attempted (esp. the auth XHR/POST) and any that
        # failed without a response. Critical for telling "CheckJC rejected
        # us" apart from "we never even submitted the form" — the latter
        # shows up as zero auth requests here.
        self._request_events = []
        self._request_failures = []
        # Snapshot of the login form elements (button/inputs) taken right
        # before submit: tag, type, whether inside a <form>, value length.
        # Tells us how the form is meant to be submitted and whether Stencil
        # actually saw the values we typed.
        self._form_debug = []

    def __enter__(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation mode enabled for {self.username}")
            return self

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                # New headless mode: behaves like headful Chrome and, crucially,
                # drops the "HeadlessChrome" token from the UA and Sec-CH-UA
                # client hints that InfoJC's IDS blacklisted (report 28/05/2026).
                "--headless=new",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        # Derive the fingerprint from the REAL engine version so UA,
        # Sec-CH-UA and navigator.userAgentData all agree with the Chromium
        # that's actually running (rebrowser-playwright may bundle a different
        # version than we hardcoded). Falls back to the module default.
        try:
            engine_version = self._browser.version or ""
            major = engine_version.split(".")[0] or _CHROME_MAJOR
        except Exception:
            engine_version = "?"
            major = _CHROME_MAJOR
        self._chrome_ua, self._sec_ch_ua, self._stealth_script = (
            _fingerprint_for_major(major)
        )
        # Small viewport randomization so two consecutive sessions don't
        # produce identical client-side fingerprints. Stays close enough
        # to 1280x800 that layout assumptions still hold.
        viewport_w = 1280 + random.randint(-40, 40)
        viewport_h = 800 + random.randint(-30, 30)
        self._context = self._browser.new_context(
            user_agent=self._chrome_ua,
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": viewport_w, "height": viewport_h},
            extra_http_headers={
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                # Client hints coherent with the UA. Without these the browser
                # could still emit a "HeadlessChrome" Sec-CH-UA or a platform
                # that contradicts the UA string.
                "Sec-CH-UA": self._sec_ch_ua,
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": _SEC_CH_UA_PLATFORM,
            },
        )
        self._context.add_init_script(self._stealth_script)
        self._context.set_default_timeout(self._timeout_ms)
        self._page = self._context.new_page()
        self._cdp = self._context.new_cdp_session(self._page)
        self._install_diagnostic_listeners()
        logger.info(
            "Chromium iniciado para %s (engine=%s, UA major=%s, viewport=%dx%d)",
            self.username, engine_version, major, viewport_w, viewport_h,
        )
        return self

    # Cap how much we retain so the buffers can't grow without bound on a
    # long-lived context (these are best-effort diagnostics, not a full HAR).
    _MAX_NET_EVENTS = 80
    _MAX_CONSOLE_EVENTS = 120
    _MAX_PAGE_ERRORS = 40
    _MAX_BODY_CHARS = 8000
    # Resource types whose response body is worth keeping. Static assets
    # (image/stylesheet/font/script) are noise; the auth call is an
    # xhr/fetch and the page itself is a document.
    _BODY_RESOURCE_TYPES = ("xhr", "fetch")
    # Substrings that mark a request as login/auth-related so we can log it
    # loudly to stdout (not just the dump) the moment it comes back.
    _AUTH_URL_HINTS = ("login", "auth", "session", "token", "signin")

    def _install_diagnostic_listeners(self):
        """Attach response/console/pageerror listeners that feed the dump.

        Best-effort: every handler swallows its own exceptions so a problem
        capturing diagnostics can never break the real login flow.
        """

        def _on_response(response):
            try:
                req = response.request
                rtype = req.resource_type
                url = response.url
                status = response.status
                ctype = response.headers.get("content-type", "")
                body = None
                if rtype in self._BODY_RESOURCE_TYPES:
                    try:
                        body = response.text()
                        if body and len(body) > self._MAX_BODY_CHARS:
                            body = body[: self._MAX_BODY_CHARS] + "…[truncated]"
                    except Exception:
                        body = "<body unavailable>"
                self._net_events.append({
                    "method": req.method,
                    "url": url,
                    "status": status,
                    "type": rtype,
                    "content_type": ctype,
                    "body": body,
                })
                if len(self._net_events) > self._MAX_NET_EVENTS:
                    del self._net_events[: -self._MAX_NET_EVENTS]
                # Surface auth-related XHRs to stdout immediately — this is
                # the call that decides accept/reject, so we want it in the
                # live logs even if the dump is later lost with the container.
                low = url.lower()
                if rtype in self._BODY_RESOURCE_TYPES and any(
                    h in low for h in self._AUTH_URL_HINTS
                ):
                    logger.info(
                        "Auth XHR for %s: %s %s -> %d (%s) body=%s",
                        self.username, req.method, url, status, ctype,
                        (body or "")[:1000],
                    )
            except Exception:
                pass

        def _on_request(request):
            try:
                rtype = request.resource_type
                # Keep only meaningful requests: the auth call (xhr/fetch),
                # navigations (document), and anything that isn't a plain GET.
                # Static asset GETs (css/js/img/font) are noise here.
                if rtype in ("xhr", "fetch", "document") or request.method != "GET":
                    self._request_events.append(
                        f"{request.method} [{rtype}] {request.url}"
                    )
                    if len(self._request_events) > self._MAX_NET_EVENTS:
                        del self._request_events[: -self._MAX_NET_EVENTS]
            except Exception:
                pass

        def _on_request_failed(request):
            try:
                failure = request.failure
                self._request_failures.append(
                    f"{request.method} [{request.resource_type}] {request.url} "
                    f"-> {failure or 'failed'}"
                )
                if len(self._request_failures) > self._MAX_NET_EVENTS:
                    del self._request_failures[: -self._MAX_NET_EVENTS]
            except Exception:
                pass

        def _on_console(msg):
            try:
                self._console_events.append(f"[{msg.type}] {msg.text}")
                if len(self._console_events) > self._MAX_CONSOLE_EVENTS:
                    del self._console_events[: -self._MAX_CONSOLE_EVENTS]
            except Exception:
                pass

        def _on_page_error(err):
            try:
                self._page_errors.append(str(err))
                if len(self._page_errors) > self._MAX_PAGE_ERRORS:
                    del self._page_errors[: -self._MAX_PAGE_ERRORS]
            except Exception:
                pass

        try:
            self._page.on("request", _on_request)
            self._page.on("requestfailed", _on_request_failed)
            self._page.on("response", _on_response)
            self._page.on("console", _on_console)
            self._page.on("pageerror", _on_page_error)
        except Exception as exc:
            logger.warning(
                "Could not install diagnostic listeners for %s: %s",
                self.username, exc,
            )

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

        # Hard cap at 2 total attempts (1 retry) regardless of config:
        # InfoJC's IDS flagged "rapid consecutive login requests" as one
        # of the lockout reasons, so we never want to hit /login more
        # than twice in a session even if the operator raises the env.
        configured_retries = max(0, get_checkjc_lite_retries())
        max_attempts = min(configured_retries + 1, 2)
        retry_base_ms = get_checkjc_lite_retry_seconds() * 1000

        user_node = pass_node = btn_node = None
        last_body_size = None
        for attempt in range(1, max_attempts + 1):
            logger.info(
                f"Navigating to {self.login_url} (attempt {attempt}/{max_attempts})"
            )
            self._page.goto(self.login_url, wait_until="networkidle")
            # Hidratación de Stencil + render del template shadow DOM closed.
            # Slight randomization so two sessions don't have an identical
            # post-goto wait fingerprint.
            self._page.wait_for_timeout(2000 + random.randint(0, 500))

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
                    # Exponential backoff with jitter so we never hit
                    # /login again in <60s. Mitigates the "rapid retries"
                    # flag the IDS picked up.
                    backoff_ms = retry_base_ms * (2 ** (attempt - 1))
                    backoff_ms += random.randint(0, 20_000)
                    logger.warning(
                        "Lite variant for %s (body=%d bytes, attempt %d/%d); "
                        "sleeping %.1fs before retry",
                        self.username, body_size, attempt, max_attempts,
                        backoff_ms / 1000,
                    )
                    self._page.wait_for_timeout(backoff_ms)
                    continue
                # Body normal pero form no encontrado: cambio de DOM real,
                # no se arregla esperando. Propagar tal cual.
                raise

        if user_node is None or pass_node is None or btn_node is None:
            # Defensive: salimos del bucle sin éxito ni excepción.
            raise CheckJCFormError(
                f"Login attempts exhausted for {self.username} "
                f"(last body size: {last_body_size} bytes). "
                f"CheckJC served a 'lite' anti-bot variant; the operator "
                f"opted for zero retries to avoid the multi-/login pattern "
                f"that triggered the May 2026 lockout. Try the next "
                f"scheduled fichaje or check from the CheckJC web UI."
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

        # Rellenar inputs con eventos de teclado reales (no Input.insertText).
        # CheckJC v7.4 puede observar la ausencia de keydown/keyup/input por JS
        # del propio Stencil; con insertText el listener interno solo veía un
        # cambio de value sin cadena de eventos, lo que figuraba en el informe
        # de InfoJC como "manipulación de campos". `page.keyboard.type` dispara
        # la secuencia completa que un humano produciría.
        self._human_type_into(user_node, self.username)
        # Tab-like pause between fields.
        self._page.wait_for_timeout(random.randint(150, 400))
        self._human_type_into(pass_node, self.password)

        # Submit like a human: press Enter while the password field still has
        # focus, IMMEDIATELY after the last char — no CDP calls in between.
        #
        # The logs proved the live password is a Stencil "controlled" input
        # that reconciles back to EMPTY ~1s after we type (val_len 14 at T,
        # 0 at T+1s). Anything we did between typing and submitting (snapshot
        # describe, dispatch synthetic events, re-resolve nodes, mouse warmup,
        # the 15s button poll) gave it time to clear, so native `required`
        # validation aborted the POST ("Please fill out this field").
        #
        # Pressing Enter right now fires the form's native implicit submission
        # while the value is still present, and every event stays
        # isTrusted=true — no field manipulation, the most human path. The
        # submit button (#btn-login) is already enabled (webdriver=false), and
        # implicit submission activates it without needing a click.
        self._page.keyboard.press("Enter")
        logger.info("Submitted login via Enter for %s", self.username)

        # Diagnostics AFTER the submit (the value may already have reconciled
        # to empty by the time these reads run — that's expected). The real
        # success signal is whether a POST to /login shows up in REQUESTS
        # ATTEMPTED, not these snapshots.
        self._form_debug = [
            f"user_input:    {self._describe_node(user_node)}",
            f"pass_input:    {self._describe_node(pass_node)}",
            f"login_button:  {self._describe_node(btn_node)}",
            f"form_element:  {self._describe_form(btn_node)}",
            "submit_method: keyboard Enter (immediate, isTrusted)",
        ]
        for line in self._form_debug:
            logger.info("FORM DEBUG %s -> %s", self.username, line)

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
            # Persist the full failure context BEFORE raising so future
            # debugging can compare what CheckJC actually returned
            # against the page we expected. Overwrites the previous
            # dump for this user; disk footprint stays bounded.
            self._persist_login_failure_dump(body_after, last_body_size)
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
                f"Dump saved to /var/log/checktime/login_failures/{self.username}.{{html,png,txt}}. "
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
            # Humanize captcha timing — a real user spends a few seconds
            # READING the distorted captcha before starting to click, and
            # ~0.5-1.5s per click finding the right keypad button. The
            # previous timing (~140ms between clicks, no read pause) was
            # one of the most obvious bot fingerprints in the InfoJC log.
            read_min = max(0, get_captcha_read_delay_min_ms())
            read_max = max(read_min, get_captcha_read_delay_max_ms())
            self._page.wait_for_timeout(random.randint(read_min, read_max))

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
            # "Verifying my input" pause before submitting.
            sub_min = max(0, get_captcha_submit_delay_min_ms())
            sub_max = max(sub_min, get_captcha_submit_delay_max_ms())
            self._page.wait_for_timeout(random.randint(sub_min, sub_max))
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

        # Humanizing browsing pattern before clicking: scroll down a bit
        # (as if reading the dashboard), pause, scroll back up, pause
        # again. A real user lands on /portal/employee, looks around, and
        # then clicks. The previous behavior ("landed → clicked btn-check
        # within 200ms") was a tell. Best-effort: any failure here is
        # swallowed so the fichaje itself never blocks on cosmetics.
        try:
            self._page.mouse.wheel(0, random.randint(120, 320))
            self._page.wait_for_timeout(random.randint(700, 1800))
            self._page.mouse.wheel(0, -random.randint(80, 240))
            self._page.wait_for_timeout(random.randint(400, 1100))
        except Exception:
            pass

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

    def _persist_login_failure_dump(self, body_html, last_body_size):
        """Save HTML, screenshot, and metadata of a failed login submit.

        Called from the PWTimeout handler in login(). Writes three files,
        all overwritten on every failure for the same user so disk usage
        stays bounded:

        - /var/log/checktime/login_failures/<user>.html
        - /var/log/checktime/login_failures/<user>.png   (viewport only)
        - /var/log/checktime/login_failures/<user>.txt   (small metadata)

        Best-effort: any IO error is swallowed so we never lose the
        original CheckJCLoginRejected error to a dump-write exception.
        """
        try:
            import os as _os
            from datetime import datetime as _dt
            dump_dir = "/var/log/checktime/login_failures"
            _os.makedirs(dump_dir, exist_ok=True)
            safe_user = re.sub(r"[^A-Za-z0-9._-]", "_", self.username or "unknown")
            base = _os.path.join(dump_dir, safe_user)
            # HTML — what CheckJC actually served after our submit
            try:
                with open(base + ".html", "w", encoding="utf-8") as f:
                    f.write(body_html or "")
            except Exception as exc:
                logger.warning("Could not write login failure HTML for %s: %s",
                               self.username, exc)
            # Screenshot — full page so banners/toasts below the fold are
            # captured too, not just the viewport. The reject reason is
            # sometimes a toast that renders at the bottom of the document.
            try:
                self._page.screenshot(path=base + ".png", full_page=True)
            except Exception as exc:
                logger.warning("Could not screenshot login failure for %s: %s",
                               self.username, exc)
            # Metadata sidecar — quick at-a-glance summary, now including the
            # network trace (auth XHR status + body), browser console, and
            # any uncaught JS errors. This is the part that tells us WHY the
            # login was rejected when the credentials are valid on the web.
            try:
                cookies = self._context.cookies() if self._context else []
                lines = [
                    f"timestamp: {_dt.now().isoformat()}",
                    f"user: {self.username}",
                    f"subdomain: {self.subdomain}",
                    f"final_url: {self._page.url}",
                    f"login_page_body_size: {last_body_size}",
                    f"after_submit_body_size: {len(body_html or '')}",
                    f"user_agent: {self._chrome_ua}",
                    f"cookies_count: {len(cookies)}",
                    f"cookie_names: {[c.get('name') for c in cookies]}",
                    "",
                    "=== PAGE ERRORS (uncaught JS) ===",
                ]
                lines += self._page_errors or ["(none)"]
                lines += ["", "=== LOGIN FORM ELEMENTS (at submit time) ==="]
                lines += self._form_debug or ["(not captured)"]
                lines += ["", "=== CONSOLE ==="]
                lines += self._console_events or ["(none)"]
                # Requests we actually attempted. If the auth POST/XHR is
                # absent here, the form never submitted (client-side block)
                # rather than CheckJC rejecting valid credentials.
                lines += ["", "=== REQUESTS ATTEMPTED (xhr/fetch/doc + non-GET) ==="]
                lines += self._request_events or ["(none)"]
                lines += ["", "=== REQUESTS FAILED (no response) ==="]
                lines += self._request_failures or ["(none)"]
                # Responses. Skip static-asset GETs (css/js/img/font) so the
                # auth call and navigations aren't buried; count the omitted.
                lines += ["", "=== NETWORK (responses) ==="]
                if self._net_events:
                    static_types = {"stylesheet", "script", "image", "font", "media"}
                    omitted = 0
                    for ev in self._net_events:
                        if ev["type"] in static_types and ev["method"] == "GET":
                            omitted += 1
                            continue
                        lines.append(
                            f"{ev['status']} {ev['method']} [{ev['type']}] "
                            f"{ev['url']}  ({ev['content_type']})"
                        )
                        if ev.get("body"):
                            lines.append(f"    body: {ev['body']}")
                    if omitted:
                        lines.append(f"(+ {omitted} static asset GET responses omitted)")
                else:
                    lines.append("(none captured)")
                with open(base + ".txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            except Exception as exc:
                logger.warning("Could not write login failure metadata for %s: %s",
                               self.username, exc)
            logger.info(
                "Login failure dump saved for %s at %s.{html,png,txt} "
                "(%d net events, %d console, %d page errors)",
                self.username, base, len(self._net_events),
                len(self._console_events), len(self._page_errors),
            )
        except Exception as exc:
            # Outer catch-all so the dump never breaks the real error path.
            logger.warning("Login failure dump failed for %s: %s",
                           self.username, exc)

    def _cdp_focus(self, node_id):
        self._cdp.send("DOM.focus", {"nodeId": node_id})

    def _human_type_into(self, node_id, text: str):
        """Focus the field with a REAL mouse click, then type it
        character-by-character via the Page keyboard so real
        keydown/keypress/keyup events fire.

        We focus with an actual mouse click (move -> press -> release on the
        field) instead of CDP `DOM.focus`. The Stencil `<sd-login>` component
        only starts tracking a field's value after a *genuine* focus/click
        interaction; with programmatic focus its internal state stayed empty
        and the submit button (#btn-login) never enabled. A real click is the
        honest, human way to hand the field focus — no field/control forcing.

        `Input.insertText` is avoided on purpose (InfoJC flagged it as
        "manipulation of fields"); per-char random delay also kills the
        constant-cadence fingerprint.
        """
        try:
            # Travel the pointer to the field like a human (curved-ish path,
            # not a teleport) and then click it. Both the movement and the
            # click go through CDP's input pipeline, so every event carries
            # isTrusted=true — indistinguishable from a physical mouse at the
            # JS level, which is the most "real" interaction automation can
            # produce.
            self._human_mouse_warmup_to(node_id)
            self._cdp_click(node_id)
        except Exception as exc:
            logger.warning("Real click to focus failed for %s (%s); "
                           "falling back to DOM.focus", self.username, exc)
            self._cdp_focus(node_id)
        # Small settle so the component registers the focus before keys.
        self._page.wait_for_timeout(random.randint(120, 300))
        delay_min = max(0, get_keystroke_delay_min_ms())
        delay_max = max(delay_min, get_keystroke_delay_max_ms())
        for ch in text:
            self._page.keyboard.type(ch)
            if delay_max > 0:
                self._page.wait_for_timeout(random.randint(delay_min, delay_max))

    def _human_mouse_warmup_to(self, node_id):
        """Move the mouse from (roughly) wherever it is toward the node's
        center via 2-3 intermediate points before the eventual click.

        We don't need precision — the click itself is dispatched via CDP
        at exact coordinates anyway. Goal is only to break the "no mouse
        movement ever" signal that headless automations leak.
        """
        try:
            box = self._cdp.send("DOM.getBoxModel", {"nodeId": node_id})
            c = box["model"]["content"]
            target_x = (c[0] + c[2]) / 2
            target_y = (c[1] + c[5]) / 2
        except Exception:
            return
        # Start somewhere "elsewhere on the page". Random but bounded.
        start_x = random.randint(50, 400)
        start_y = random.randint(50, 300)
        steps = random.randint(2, 4)
        try:
            self._page.mouse.move(start_x, start_y)
            for i in range(1, steps + 1):
                interp_x = start_x + (target_x - start_x) * (i / steps)
                interp_y = start_y + (target_y - start_y) * (i / steps)
                # Slight noise off the straight line.
                interp_x += random.uniform(-6, 6)
                interp_y += random.uniform(-6, 6)
                self._page.mouse.move(interp_x, interp_y)
                self._page.wait_for_timeout(random.randint(40, 110))
        except Exception:
            # Mouse movement is purely cosmetic — never block the click on it.
            pass

    def _cdp_click(self, node_id):
        """Envía un click real en el centro del box del nodo. Funciona aunque
        el nodo viva dentro de un shadow root closed: las coordenadas son
        globales (layout/page coordinates, same as getBoundingClientRect on
        an unscrolled page).
        """
        box = self._cdp.send("DOM.getBoxModel", {"nodeId": node_id})
        c = box["model"]["content"]
        x = (c[0] + c[2]) / 2
        y = (c[1] + c[5]) / 2
        logger.info("CDP click at (%.0f, %.0f) for nodeId=%s", x, y, node_id)
        self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y, "buttons": 0,
        })
        self._page.wait_for_timeout(random.randint(40, 120))
        self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": "left", "buttons": 1, "clickCount": 1,
        })
        self._page.wait_for_timeout(random.randint(40, 120))
        self._cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": "left", "buttons": 0, "clickCount": 1,
        })

    def _dispatch_input_events(self, node_id):
        """Re-fire input/change/keyup on a node so a framework that attached
        its validation listener AFTER our initial keystrokes (late Stencil
        hydration) re-evaluates the form and enables the submit button.

        Best-effort: swallows its own errors so it never breaks login.
        """
        try:
            obj = self._cdp.send("DOM.resolveNode", {"nodeId": node_id})
            oid = obj["object"]["objectId"]
            fn = (
                "function(){"
                "this.dispatchEvent(new Event('input',{bubbles:true}));"
                "this.dispatchEvent(new Event('change',{bubbles:true}));"
                "this.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));"
                "return true;}"
            )
            self._cdp.send("Runtime.callFunctionOn", {
                "objectId": oid,
                "functionDeclaration": fn,
                "returnByValue": True,
            })
        except Exception as exc:
            logger.warning("Could not dispatch input events for %s: %s",
                           self.username, exc)

    def _value_length(self, node_id):
        """Return len(node.value) for an input, or None if it can't be read.

        Used to verify the LIVE form fields actually hold our typed input
        before submitting (Stencil re-hydration can swap the input nodes,
        leaving the mounted form empty and the native `required` validation
        blocking the POST). Reads the live `.value` property, not the HTML
        attribute, so it reflects what the user "sees" in the field."""
        try:
            obj = self._cdp.send("DOM.resolveNode", {"nodeId": node_id})
            oid = obj["object"]["objectId"]
            res = self._cdp.send("Runtime.callFunctionOn", {
                "objectId": oid,
                "functionDeclaration":
                    "function(){return (typeof this.value==='string')"
                    "?this.value.length:0;}",
                "returnByValue": True,
            })
            return res.get("result", {}).get("value")
        except Exception:
            return None

    def _set_value_js(self, node_id, text: str):
        """Force-set an input's value when click+keyboard typing won't stick.

        We saw the live password field stay empty (val_len 0) even after a
        real click-to-focus + per-char keyboard typing — the focus apparently
        didn't land on the mounted Stencil-controlled node, so the keystrokes
        went nowhere and native `required` validation blocked the POST. Since
        the anti-bot button gate is already satisfied at this point (button
        enabled), the remaining problem is purely mechanical: get the value
        into the element the form will submit.

        We use the element's NATIVE value setter (the React/Stencil trick:
        frameworks patch the instance `value`, so calling the prototype's
        original setter is what makes their internal value tracker register
        the change) and then fire input/change/keyup so both the framework
        and the browser's constraint validation see a non-empty field.

        Returns the resulting value length, or None on failure."""
        try:
            obj = self._cdp.send("DOM.resolveNode", {"nodeId": node_id})
            oid = obj["object"]["objectId"]
            fn = (
                "function(v){"
                "const setter=Object.getOwnPropertyDescriptor("
                "  window.HTMLInputElement.prototype,'value');"
                "if(setter&&setter.set){setter.set.call(this,v);}"
                "else{this.value=v;}"
                "this.dispatchEvent(new Event('input',{bubbles:true}));"
                "this.dispatchEvent(new Event('change',{bubbles:true}));"
                "this.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));"
                "return (typeof this.value==='string')?this.value.length:0;}"
            )
            res = self._cdp.send("Runtime.callFunctionOn", {
                "objectId": oid,
                "functionDeclaration": fn,
                "arguments": [{"value": text}],
                "returnByValue": True,
            })
            return res.get("result", {}).get("value")
        except Exception as exc:
            logger.warning("JS value-set failed for %s: %s", self.username, exc)
            return None

    def _button_disabled(self, node_id):
        """Return True/False for the node's `disabled` state, or None if it
        can't be read. Lightweight (used in the enable poll loop)."""
        try:
            obj = self._cdp.send("DOM.resolveNode", {"nodeId": node_id})
            oid = obj["object"]["objectId"]
            res = self._cdp.send("Runtime.callFunctionOn", {
                "objectId": oid,
                "functionDeclaration": "function(){return !!this.disabled;}",
                "returnByValue": True,
            })
            return res.get("result", {}).get("value")
        except Exception:
            return None

    def _describe_node(self, node_id):
        """Return a short JSON description of a DOM node (tag, type, id,
        class, value length, disabled, form ancestor, truncated outerHTML).

        Used purely for diagnostics so a failed-login dump reveals how the
        login form is wired. Never raises — returns an error string instead.
        Note: for the password we record only the VALUE LENGTH, never the
        value itself, so the secret never lands in a dump.
        """
        try:
            obj = self._cdp.send("DOM.resolveNode", {"nodeId": node_id})
            oid = obj["object"]["objectId"]
            fn = (
                "function(){try{return JSON.stringify({"
                "tag:this.tagName,"
                "type:(this.getAttribute&&this.getAttribute('type'))||null,"
                "id:this.id||null,"
                "cls:this.className||null,"
                "val_len:(typeof this.value==='string'?this.value.length:null),"
                "disabled:!!this.disabled,"
                "in_form:(this.closest&&this.closest('form'))?true:false,"
                "html:(this.outerHTML||'').slice(0,400)"
                "});}catch(e){return 'err:'+e;}}"
            )
            res = self._cdp.send("Runtime.callFunctionOn", {
                "objectId": oid,
                "functionDeclaration": fn,
                "returnByValue": True,
            })
            return res.get("result", {}).get("value")
        except Exception as exc:
            return f"<describe failed: {exc}>"

    def _describe_form(self, btn_node_id):
        """Return action/method/enctype of the <form> ancestor of btn_node_id.

        In the lite anti-bot variant the form may have action='' or no method,
        which means a native submit would GET the current URL instead of POSTing
        to the auth endpoint — explaining why we see no POST in REQUESTS ATTEMPTED.
        """
        try:
            obj = self._cdp.send("DOM.resolveNode", {"nodeId": btn_node_id})
            oid = obj["object"]["objectId"]
            fn = (
                "function(){try{"
                "var f=this.closest('form');"
                "if(!f)return 'no <form> ancestor';"
                "return JSON.stringify({"
                "action:f.getAttribute('action'),"
                "method:f.getAttribute('method')||f.method,"
                "enctype:f.getAttribute('enctype'),"
                "id:f.id||null,"
                "cls:f.className||null,"
                "html:f.outerHTML.slice(0,600)"
                "});"
                "}catch(e){return 'err:'+e;}}"
            )
            res = self._cdp.send("Runtime.callFunctionOn", {
                "objectId": oid,
                "functionDeclaration": fn,
                "returnByValue": True,
            })
            return res.get("result", {}).get("value")
        except Exception as exc:
            return f"<describe_form failed: {exc}>"

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
        # Between-click pause. Default 400-1200ms — slower than a bot
        # banging out clicks (which is what the previous 140-280ms looked
        # like) and within the lower band of a human finding the next
        # keypad button. Also gives CheckJC's JS time to re-shuffle.
        click_min = max(0, get_captcha_click_delay_min_ms())
        click_max = max(click_min, get_captcha_click_delay_max_ms())
        self._page.wait_for_timeout(random.randint(click_min, click_max))

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

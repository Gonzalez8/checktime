# Migración a CheckJC v7.4 (mayo 2026)

> Releases involucradas: v1.5.0 a v1.5.4 (v1.5.4 es la estable en producción).

## TL;DR

CheckJC publicó la versión 7.4 alrededor del 13 de mayo de 2026. El cambio
introdujo Stencil + Declarative Shadow DOM `closed` en el formulario de
login y detección activa de clientes no-navegador. Esto rompió el scraper
basado en Selenium que llevaba dos años funcionando.

La solución fue migrar a Playwright + Chromium real, atravesando el shadow
DOM closed mediante CDP (Chrome DevTools Protocol). Cualquier intento de
hablar con CheckJC sin un navegador completo (urllib, curl, curl_cffi
imitando Chrome 147, Playwright `request`) es rechazado en silencio,
independientemente de la IP o los headers.

## Cronología

| Fecha | Hito |
|---|---|
| ~2026-05-13 | CheckJC despliega v7.4 |
| 2026-05-13 / 14 | El scheduler empieza a fallar cada hora. Llega a Telegram un stack hex sin mensaje. Los logs internos no aparecen en `docker logs` por un bug de configuración no relacionado |
| 2026-05-15 | Diagnóstico, varios falsos positivos descartados (versiones Chrome/chromedriver, zombis, IP block, case-sensitive, TLS) |
| 2026-05-15 | v1.5.4 estable: Playwright + Chromium real con CDP |

## Síntomas

Telegram recibía mensajes con esta pinta:

```
❌ Error during check in for user Jose: Message:
Stacktrace:
#0 0x5624fe85ea9e <unknown>
#1 0x5624fe2f4ec1 <unknown>
...
```

Un `WebDriverException` con `Message` vacío y stacktrace hex puro del binario
de chromedriver. Sin contexto.

Adicionalmente:

- `docker logs` no mostraba las trazas del scheduler aunque Telegram sí
  recibía los avisos (ver "Bug colateral: logging silenciado" más abajo).
- El mensaje decía "Error during check **in**" aunque el fallo real era de
  `login()`. Es solo cómo `service.py` lo formatea.

## Cambio real en CheckJC

Cargar `https://<subdomain>.checkjc.com/login` con un navegador devuelve un
HTML donde el form de login vive dentro de:

```html
<sd-login class="login">
    <template shadowrootmode="closed" shadowrootdelegatesfocus>
        ...
        <input name="<RANDOM>" class="form-control form_username" .../>
        <input name="<RANDOM>" class="form-control form_password" type="password" .../>
        <input name="token" type="hidden" value="<512-char string>" />
        <button id="btn-login" type="submit">...</button>
        ...
    </template>
</sd-login>
```

Tres cosas hostiles para un scraper que ya estaba en producción:

1. **Declarative Shadow DOM closed**. El navegador convierte el `<template
   shadowrootmode="closed">` en un shadow root al parsear el HTML, no a
   través de `attachShadow()` JS. Selenium `By.CSS_SELECTOR` no atraviesa
   shadow roots closed.
2. **Nombres de campos aleatorios por render**. El `name` de los inputs
   cambia en cada GET. No se puede hard-codear.
3. **17 copias del form en SSR**. El servidor renderiza el mismo `<sd-login>`
   17 veces seguidas (presumiblemente para confundir). Solo una es visible.

Además, el botón `#btn-check` del dashboard sigue en light DOM pero está
oculto por la clase `hidden-soft` hasta que `/rest/portal/employee/liveData.json`
responde con la configuración del usuario. Si lo buscas inmediatamente
después de navegar al portal, no es interactuable.

## Por qué no sirvió un cliente HTTP

Sería tentador (y barato) abandonar Selenium y hablar directamente con
CheckJC vía HTTP, replicando lo que hace el navegador. Lo intentamos y
**no funciona**. CheckJC rechaza el POST de login con 302 a `/login` (sin
banner, sin pista) si detecta que el cliente no es un navegador completo.

Probado y descartado:

| Cliente | TLS | HTTP | IP | Resultado |
|---|---|---|---|---|
| `urllib` (Python stdlib) | Python TLS | 1.1 | residencial | 302 → /login |
| `urllib` con todos los headers de Chrome | Python TLS | 1.1 | residencial | 302 → /login |
| `urllib` con +5s de delay entre GET y POST | Python TLS | 1.1 | residencial | 302 → /login |
| `curl` con todos los headers | libcurl | 2 | residencial | 200 con HTML "lite" |
| `curl_cffi` (impersonate Chrome 147) | Chrome 147 | 3 (QUIC) | residencial | 302 → /login |
| `curl_cffi` desde NordVPN España | Chrome 147 | 3 | NordVPN ES | 302 → /login |
| `curl_cffi` desde NordVPN Portugal | Chrome 147 | 3 | NordVPN PT | 302 → /login |
| `curl_cffi` desde IP residencial fresca | Chrome 147 | 3 | nueva | 302 → /login |
| **Chromium real (Playwright)** | Chrome | 2 | residencial | **302 → /portal/employee ✅** |

La detección de CheckJC va más allá de TLS fingerprint, headers HTTP y
HTTP/2/3. Mide algo del runtime del navegador (ejecución de JS, descarga
de assets, comportamiento de eventos) que no se puede emular sin abrir
un navegador.

## Hipótesis descartadas (que parecían plausibles)

Útil documentarlo para que el siguiente que persiga un fallo parecido no
gaste tiempo en ellas:

- **Mismatch entre Chromium y chromedriver**: ambas versiones iguales.
- **Procesos zombi de Chrome o leftover de perfiles `/tmp/chrome_*`**:
  el contenedor estaba limpio.
- **Imagen Docker recientemente rebuildeada sin avisar**: el contenedor
  llevaba 2 meses arriba con la misma imagen.
- **CheckJC con username case-sensitive**: el server normaliza el case.
  La confusión vino de un único éxito casual con `z` minúscula seguido
  de fallos cuando ya estaba escalando el lockout de IP.
- **CheckJC con captcha o MFA**: ni captcha ni MFA en este tenant.
- **CheckJC con rate-limit puro por IP**: el banner de IP bloqueada sí
  aparece tras varios fallos, pero hay también un rechazo silencioso
  previo (302 sin banner) que se confunde con credenciales malas.
- **Cliente HTTP detectado por User-Agent**: aunque el UA es necesario,
  no es suficiente. Hay detección más profunda.

## La solución

`src/checktime/scheduler/checker.py` ahora:

1. Lanza Chromium headless mediante Playwright en `__enter__`.
2. En `login()`:
   - Navega a `/login`, espera a la hidratación del componente Stencil.
   - Verifica si hay banner de IP bloqueada (y lanza `CheckJCIPBlocked`
     con los minutos exactos que reporta el server).
   - Pide a Chromium el árbol DOM completo con
     `DOM.getDocument({depth: -1, pierce: true})` vía CDP. El flag
     `pierce: true` es clave: incluye los shadow roots aunque sean closed.
   - Encuentra los nodos del primer `.form_username`, `.form_password` y
     `#btn-login` visibles (filtrados con `DOM.getBoxModel`).
   - Inyecta el texto con `DOM.focus` + `Input.insertText`.
   - Click real en el botón con `Input.dispatchMouseEvent` en las
     coordenadas del centro del botón.
   - Espera a `wait_for_url(lambda url: "/login" not in url)`.
3. En `perform_check()`:
   - Si no estamos ya en `/portal/employee`, navega.
   - Espera a que `#btn-check` sea visible (timeout 15s) porque el JS lo
     muestra solo tras una llamada AJAX a `liveData.json`.
   - Click con `page.click("#btn-check")` — este botón sí está en light
     DOM y Playwright lo maneja sin CDP.
   - Espera 3s a que la UI procese el submit.

El servicio `service.py` no necesita ningún cambio: la interfaz pública
de `CheckJCClient` (`__enter__`, `login`, `check_in`, `check_out`,
`__exit__`) es la misma que antes.

## Diagnóstico de errores

`checker.py` lanza excepciones tipadas; `service.py` las formatea en
mensajes diferenciados para Telegram:

| Excepción | Telegram | Causa probable |
|---|---|---|
| `CheckJCIPBlocked` | 🚫 | Lockout activo. El mensaje incluye los minutos exactos del banner |
| `CheckJCLoginRejected` | 🚧 | El navegador hizo submit pero el server lo devolvió a `/login`. Puede ser credenciales malas o rate-limit silencioso previo al banner |
| `CheckJCSessionLost` | ⏳ | La sesión se perdió entre login y check (redirect a `/logout`) |
| `CheckJCFormError` | 🧩 | No se localizó un elemento esperado. CheckJC probablemente cambió el HTML — revisar este documento como punto de partida |
| `CheckJCUnexpectedResponse` | ❓ | Status HTTP inesperado |
| Cualquier otra | ❌ | Timeout de red, Playwright crash, etc. |

## Bug colateral: logging silenciado

Durante el diagnóstico nos sorprendió que Telegram recibía errores pero
`docker logs` no mostraba la traza Python correspondiente. La causa:
`logging.basicConfig(...)` en `service.py` es **no-op silencioso si el
root logger ya tiene handlers**. Como `service.py` importa
`checktime.web.create_app` antes de configurar logging, Flask (o sus
extensiones) ya añaden un handler al root logger y nuestro `basicConfig`
se ignora. Resultado: `logger.error(...)` no llega ni a stdout ni al
fichero, pero el `telegram_client.send_message(...)` que viene después
sí funciona.

Solución: usar `logging.basicConfig(..., force=True)` (Python 3.8+). El
parámetro `force=True` elimina los handlers existentes y aplica los
nuestros.

## Notas operativas

- **El primer fichaje tras desplegar v1.5.4 puede tardar más** porque
  Portainer descarga la nueva imagen de ~1 GB.
- Si llega 🚫 `CheckJCIPBlocked` en el primer intento, es el lockout
  residual de los días previos en los que el scheduler fallaba cada
  hora. Se libera solo (los minutos vienen en el mensaje) y no se
  vuelve a triggerar porque el nuevo checker no falla.
- Si llega 🧩 `CheckJCFormError`, probablemente CheckJC cambió algo
  más en el HTML. Empezar por inspeccionar `/login` con DevTools y
  comparar con esta documentación.

## Scripts de debug

En `tests/` hay tres scripts útiles si vuelve a fallar algo en este
flujo:

- `tests/debug_login.py` — login con `urllib` puro. Útil para confirmar
  que las credenciales y los selectores siguen siendo válidos en un
  cliente HTTP mínimo (aunque CheckJC lo rechace, el form se parsea).
- `tests/debug_login_curl.sh` — login con `curl` real (HTTP/2). Útil
  para descartar TLS y HTTP/2 si vuelve a haber sospecha de detección.
- `tests/debug_login_curl_cffi.py` — login con `curl_cffi` impersonando
  Chrome 147. El cliente HTTP más cercano a Chrome posible. Si esto
  empezara a entrar algún día, podríamos volver a un stack sin
  Chromium.

Todos toman tres argumentos posicionales: `USER PASSWORD SUBDOMAIN`.

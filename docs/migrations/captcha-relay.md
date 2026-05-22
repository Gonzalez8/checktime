# Captcha relay (mayo 2026, v1.8.0 → v1.8.1)

## TL;DR

CheckJC ha añadido `/portal/employee/verification` después del login:
un captcha de 6 dígitos distorsionados + teclado en pantalla que **se
baraja después de cada click**.

El scheduler no puede ya fichar solo. Implementamos un **captcha-relay
humano vía Telegram**: el scheduler manda al usuario una imagen
compuesta (captcha + teclado etiquetado 1→10), recibe **16 dígitos
en una sola respuesta** (los 10 del teclado + los 6 del captcha), los
introduce y submitea. Diseñado con un punto de extensión claro para
que en v1.9+ una IA con visión (LLM) resuelva el captcha sin
intervención humana — la misma interfaz `CaptchaSolver.solve()` sirve
para ambos.

## Por qué 16 dígitos y no solo 6

v1.8.0 intentó usar Tesseract OCR sobre las 10 imágenes limpias del
teclado para construir el mapping `letra → dígito` automáticamente,
y solo pedir 6 dígitos al usuario. Producción mostró que Tesseract
**confunde sistemáticamente 1 con 7** en este captcha, lo que genera
mappings con duplicados/faltas y rompe el flujo. Sin un modelo de
visión real, no es fiable.

v1.8.1 elimina Tesseract: el usuario lee los 10 dígitos del teclado
en orden (1→10 etiquetados en la imagen que recibe) y los 6 del
captcha, todo en una sola línea de 16 dígitos. Es +10 caracteres de
fricción a cambio de 100% de fiabilidad. Cuando se implemente el
`LLMVisionSolver`, esos 10 dígitos extra los lee el LLM y la fricción
para el usuario desaparece.

## Lo que se descubrió

Validado end-to-end contra el CheckJC real (DD/MM 22/05/2026):

1. **El captcha es una imagen JPEG distorsionada** con 6 dígitos
   (anti-OCR clásico).
2. **El teclado son 10 botones con imágenes PNG limpias** de los
   dígitos 0-9. Cada botón lleva `data-value="<LETRA>"`.
3. Las letras (`A-Z` aleatorias por sesión, ej. `N,L,I,M,X,D,O,A,T,H`)
   son **estables durante toda la sesión**. Solo cambian sus
   **posiciones** después de cada click (incluido `<`).
4. El servidor identifica el dígito pulsado por la **letra** del
   `data-value`, no por la posición.

Por tanto el bypass es:

- Identificar el mapping `letra → dígito` UNA vez por sesión (OCR de
  las 10 imágenes limpias del teclado — Tesseract trivial).
- Mostrar el captcha distorsionado a un solver (usuario humano o
  LLM con visión) y obtener los 6 dígitos.
- Para cada dígito: leer el DOM, encontrar la posición actual de
  la letra correspondiente, click.

Sin OCR en runtime entre clicks; las posiciones se releen del DOM
directamente (atributo `data-value` de cada `btn-shuffle`).

## Componentes nuevos

| Componente | Responsabilidad |
|---|---|
| `shared/models/captcha.py` | Modelo `PendingCaptcha` (cola humano-bot) |
| `scheduler/captcha_solver.py` | Interfaz `CaptchaSolver`, `TelegramHumanSolver`, stub `LLMVisionSolver` |
| `scheduler/keypad_reader.py` | OCR de los 10 botones limpios → `letra → dígito` (Tesseract) |
| `scheduler/checker.py::_solve_verification` | Orquestación: capturar imágenes → mapping → solver → clicks → submit |
| `bot/listener.py::try_handle_captcha_reply` | Bot intercepta los 6 dígitos del usuario y los escribe en DB |

## Flujo completo

```
09:00:00  Scheduler dispara fichaje
09:00:05  Login OK → /portal/employee/verification
09:00:06  CheckJCClient._solve_verification:
            - Captura imagen captcha (JPEG)
            - Captura 10 PNG del keypad + sus letras
            - Tesseract OCR → {N:3, L:7, I:1, M:8, X:2, D:9, O:4, A:5, T:6, H:0}
            - Crea PendingCaptcha(state=WAITING) en DB con imagen
            - sendPhoto a Telegram del usuario:
                "🧩 Captcha para tu fichaje de entrada
                 [imagen]
                 Responde con los 6 dígitos. ⏱ 5 minutos."
            - Inicia polling DB (1s) hasta state=ANSWERED o expiración

09:00:30  Usuario responde por Telegram: "578599"
09:00:31  Bot listener detecta:
            - Hay PendingCaptcha WAITING para este chat_id
            - "578599" son 6 dígitos válidos
            - Escribe response="578599", state=ANSWERED
            - Confirma al usuario: "✅ Recibido. Procesando..."

09:00:32  Scheduler sale del polling con response="578599"
            - Traduce dígitos → letras: A I A I C I (ejemplo)
            - Por cada letra:
                * Lee DOM actual
                * Encuentra (cx, cy) del botón con data-value=letra
                * cdp_click_at(cx, cy)
                * wait 120 ms (deja que el JS re-baraje)
            - Click submit
            - Espera salir de /verification

09:00:35  Aterrizamos en /portal/employee → btn-check → fichaje ✅
09:00:36  Telegram al usuario: "🟢 Check in completed successfully"
```

## Configuración

| Variable | Default | Notas |
|---|---|---|
| `USER_CHECK_STAGGER_SECONDS` | `60` | Heredado de v1.7.2 |
| `CHECKJC_LITE_RETRIES` | `2` | Heredado de v1.7.3 |
| `CHECKJC_LITE_RETRY_SECONDS` | `60` | Heredado de v1.7.3 |

**Captcha-relay**: TTL hardcodeado a 300 s (5 min). Si en producción se
demuestra que necesita ser configurable, exponer un getter en
`shared/config.py` con `CAPTCHA_RELAY_TIMEOUT_SECONDS` y pasarlo al
solver. No lo añado preventivamente.

## Esquema de DB

Tabla nueva creada por `db.create_all()` (no requiere ALTER TABLE):

```sql
CREATE TABLE pending_captcha (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    check_type VARCHAR(8) NOT NULL,
    state VARCHAR(16) NOT NULL DEFAULT 'WAITING',
    captcha_image BYTEA,
    response VARCHAR(8),
    attempt INT NOT NULL DEFAULT 1,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_pending_captcha_user_id ON pending_captcha(user_id);
CREATE INDEX ix_pending_captcha_state ON pending_captcha(state);
```

Estados: `WAITING → ANSWERED → CONSUMED`, o `WAITING → EXPIRED` /
`FAILED`. El bot solo escribe `ANSWERED`. El scheduler escribe
`CONSUMED` tras leer la respuesta. El bot tiene un sweeper que pasa
filas a `EXPIRED` tras pasar `expires_at`.

## Cómo plug-in del LLM (futuro)

`captcha_solver.py::LLMVisionSolver` es un stub. Para activarlo:

1. Implementar `solve()` con tu cliente LLM preferido (Anthropic /
   OpenAI / Gemini). Encoda `captcha_image_bytes` en base64 y envía
   con prompt: *"Reply ONLY with the 6 digits visible in this captcha.
   No other text."*
2. Validar que la respuesta es 6 caracteres numéricos; reintentar
   una vez si no.
3. En `service.py`, cambiar la línea:
   ```python
   captcha_solver = TelegramHumanSolver(...)
   ```
   por:
   ```python
   captcha_solver = LLMVisionSolver(...)
   # o un hybrid: primero LLM, fallback a TelegramHumanSolver si falla
   ```

El resto del código no se entera.

## Limitaciones conocidas

- **Captcha incorrecto**: si el usuario teclea mal los 6 dígitos,
  `CheckJCClient._solve_verification` reintenta UNA vez con un captcha
  nuevo. Tras el segundo fallo, lanza `CheckJCCaptchaFailed` y avisa
  por Telegram.
- **Sin Telegram configurado**: si el usuario no tiene `telegram_chat_id`
  set, el solver devuelve `None` directamente y el fichaje falla.
  Mensaje claro en logs.
- **Sesión expira mientras esperamos**: el captcha de CheckJC tiene su
  propio timer (~5 min observado en prod). Si pasa antes de que el
  usuario responda, el siguiente submit cae a `/login`. Lo manejamos
  como `CheckJCSessionLost`. No es fatal: el siguiente ciclo del
  scheduler reintenta.
- **OCR del keypad falla**: Tesseract puede equivocarse en 1 de cada
  ~50 imágenes (acentos cromáticos extraños). Si el mapping resultante
  no cubre los 10 dígitos, lanzamos `CheckJCFormError` con detalles.

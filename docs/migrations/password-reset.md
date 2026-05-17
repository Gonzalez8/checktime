# Recuperación de contraseña (mayo 2026)

## TL;DR

Se añade flujo de "olvidé mi contraseña" usando la integración de
Telegram que ya tiene CheckTime, más una página de admin para emitir
contraseñas temporales a usuarios sin Telegram.

No requiere variables de entorno nuevas ni dependencias adicionales: el
correo se descartó porque no hay SMTP configurado en el proyecto.

## Cambios en la base de datos

Dos columnas nullables nuevas en la tabla `user`:

| Columna | Tipo | Uso |
|---|---|---|
| `password_reset_token_hash` | `VARCHAR(128)` | SHA-256 hex del token (nunca se guarda el raw) |
| `password_reset_token_expires_at` | `TIMESTAMP` | Caducidad absoluta (TTL = 30 min) |

La migración se aplica **automáticamente al arrancar la web**
(`src/checktime/web/__init__.py::_apply_lightweight_migrations`) con
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Es idempotente y no requiere
acción manual en despliegues existentes.

Si por algún motivo quieres aplicarla a mano sobre Postgres:

```sql
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(128);
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password_reset_token_expires_at TIMESTAMP;
```

## Flujo de auto-servicio (Telegram)

1. El usuario va a `/auth/login` → enlace **"¿Olvidaste tu contraseña?"**.
2. Introduce su usuario **o** email en `/auth/forgot-password`.
3. El backend:
   - Busca el usuario por username o email (case-insensitive en email).
   - Si existe **y** tiene `telegram_chat_id`, genera un token aleatorio
     (`secrets.token_urlsafe(32)`), guarda su hash y caducidad, y envía
     por Telegram un enlace a `/auth/reset-password/<token>`.
   - **Siempre** muestra el mismo flash genérico (existe/no existe,
     Telegram configurado/no configurado) para evitar enumeración de
     cuentas.
4. El usuario abre el enlace, fija una nueva contraseña (validación
   mínima: 8 caracteres + confirmación) y el token se invalida.

El token caduca en 30 minutos (`PASSWORD_RESET_TOKEN_TTL_MINUTES` en
`models/user.py`). Solo se almacena el SHA-256, así que ni siquiera el
admin con acceso a la base de datos puede recuperar el token original.

## Flujo de admin (fallback para usuarios sin Telegram)

1. El admin va a `/admin/users`.
2. Pulsa **"Restablecer contraseña"** junto al usuario afectado.
3. El backend genera una contraseña aleatoria
   (`secrets.token_urlsafe(12)`), la setea como `password_hash` del
   usuario y la **muestra una sola vez** en la misma página.
4. El admin la copia y la entrega por un canal seguro (en persona,
   chat de empresa). Si recarga, desaparece — no se persiste en flash
   ni en sesión.
5. El usuario inicia sesión con ella y debe cambiarla desde
   `/auth/profile`.

`admin_reset_password` también limpia cualquier token de recuperación
pendiente, así que si el usuario tenía un enlace de Telegram pidiendo
reset, ese enlace queda inválido.

## Seguridad: notas y trade-offs

- **Hash vs encriptación**: el token se guarda hasheado (SHA-256) para
  que un volcado de DB no permita usarlo. La comparación es de tiempo
  constante con `secrets.compare_digest`.
- **Sin enumeración**: el endpoint `/auth/forgot-password` da la misma
  respuesta haya o no usuario, tenga o no Telegram.
- **TTL corto**: 30 minutos. Suficiente para que el usuario lo abra,
  pequeño suficiente para que un Telegram comprometido no quede como
  ventana eterna.
- **No hay rate-limit a nivel app**. Si CheckTime se expone a internet
  abierto, conviene poner un rate-limit (nginx, fail2ban) en
  `/auth/forgot-password` para evitar spam de Telegram. En la red
  interna donde corre hoy no es urgente.
- **El admin ve la contraseña temporal**. Es intencional: la idea es
  entregarla offline. No hay forma de evitarlo sin reintroducir SMTP.

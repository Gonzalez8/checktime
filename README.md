# CheckTime

CheckTime is a self-hosted application that automates browser‑based
check‑ins and check‑outs against [CheckJC](https://www.checkjc.com/).
It ships a Flask web UI for management, a Telegram bot for
notifications and quick actions, and a scheduler that drives a real
Chromium via Playwright. It is designed to handle CheckJC's modern
anti‑bot defences (Stencil + closed shadow DOM, lite‑variant rate
limiting, and the 6‑digit verification captcha).

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [How the CheckJC captcha is handled](#how-the-checkjc-captcha-is-handled)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Installation](#installation)
- [Usage](#usage)
  - [Web Interface](#web-interface)
  - [Telegram Bot](#telegram-bot)
- [Deployment with the prebuilt image](#deployment-with-the-prebuilt-image)
- [Change history](#change-history)
- [Screenshots](#screenshots)
- [License](#license)

---

## Features

### Automated check‑in / check‑out

- Multi‑user: each user has their own CheckJC credentials, schedule, and
  Telegram settings. Credentials are encrypted at rest.
- Multiple **schedule periods** (e.g. *Winter Hours*, *Summer Hours*)
  with different times per weekday.
- Per‑date **overrides** to adjust a single day without touching the
  recurring schedule.
- **Holidays** added one by one, by date range, or imported from a
  `.ics` calendar.
- **Stagger** between consecutive users so a single shared egress IP
  doesn't trip CheckJC's anti‑bot.
- Automatic **retry / back‑off** when CheckJC serves its stripped
  "lite" HTML; per‑user **account lockout detection** that stops
  retrying before CheckJC's threshold is hit.
- Resilient to CheckJC v7.4: closed shadow DOM is traversed via CDP,
  Stencil hydration timing is handled with bounded waits.

### CheckJC verification captcha

CheckJC v7.4+ shows a 6‑digit captcha plus a shuffling on‑screen
keypad after login. CheckTime supports **two solvers**, plugged into
the same `CaptchaSolver` interface and chosen automatically:

1. **Google Gemini** (`LLMVisionSolver`) — fully automatic. The user
   pastes a Gemini API key in their profile and the scheduler asks
   the LLM to read both the captcha and the keypad in one call.
   Default model is `gemini-2.5-flash-lite` (free tier, ~$0/month).
2. **Telegram human relay** (`TelegramHumanSolver`) — fallback when
   no API key is set or the LLM fails for any reason. The scheduler
   posts a composite image to the user's Telegram chat and waits up
   to 5 minutes for the user to reply with 16 digits.

See [the captcha section](#how-the-checkjc-captcha-is-handled) for the
visual.

### Web interface

- Calendar view with working days, holidays, overrides.
- Schedule and holiday management.
- **User profile** with: account, CheckJC credentials, Telegram, and
  Google Gemini API key + model dropdown.
- **Password recovery** with two paths:
  - Self‑service: token delivered over Telegram (no SMTP needed).
  - Admin fallback: one‑time temporary password from the admin user
    list.
- **Admin pages** (only visible for `is_admin`):
  - User list with reset‑password and delete buttons.
  - Telegram broadcast with per‑recipient checkboxes (not just
    "send to everyone").

### Telegram bot

- Real‑time notifications for successful and failed fichajes (typed
  per error class: 🟢 ok, 🚫 IP blocked, ⛔ account locked, 🧩 captcha
  failed, ⏳ session lost, ❌ unknown).
- Add / remove / list holidays via chat commands.
- Receives captcha replies and forwards them to the scheduler via the
  shared database.

---

## Architecture

```
┌──────────┐      ┌──────────────────────────────────────────┐
│ PostgreSQL │◀────┤ supervisord                              │
└──────────┘      │   ├── gunicorn (Flask web UI)            │
                  │   ├── scheduler.service (apscheduler +    │
                  │   │     Playwright + CaptchaSolver)       │
                  │   └── bot.listener (Telegram long‑poll)   │
                  └──────────────────────────────────────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ trainingX.checkjc  │
                    │ .com (real browser │
                    │ via Playwright)    │
                    └────────────────────┘
```

The web, scheduler and bot processes share the same Flask `db.session`
and business‑logic layer (`shared/services` + `shared/repository`).
The captcha relay uses a `pending_captcha` table to bridge the
scheduler (which waits for a reply) and the bot (which receives it).

Production typically runs the `app` container behind a VPN (Gluetun +
NordVPN) so CheckJC sees a known egress IP. Both compose flavours are
included.

---

## Technology Stack

- **Backend**: Python 3.11, Flask, SQLAlchemy, Flask‑Login, Flask‑WTF
- **Frontend**: Jinja2, Bootstrap 5, vanilla JS / AJAX
- **Database**: PostgreSQL 15
- **Browser automation**: Playwright + Chromium (real browser, with
  CDP for closed shadow DOM traversal)
- **LLM solver**: Google Gemini (`gemini-2.5-flash-lite` by default,
  configurable per user)
- **Image composition**: Pillow
- **Encryption at rest**: `cryptography.fernet` (CheckJC password and
  Gemini API key)
- **Deployment**: Docker, Docker Compose, Gunicorn, Supervisord;
  prebuilt images on **GitHub Container Registry**
  (`ghcr.io/gonzalez8/checktime`).

---

## How the CheckJC captcha is handled

When CheckJC redirects the post‑login flow to
`/portal/employee/verification`, the scheduler captures **the
distorted 6‑digit captcha** and **the 10 keypad button images** and
composes them into a single labelled image:

![Captcha composite shipped to the solver](docs/img/captcha-composite.png)

The format is always the same: captcha on top, keypad strip below with
the buttons indexed `1` to `10` left to right. From that single
image, a solver returns the **6 letters** to click in order.

Why letters and not digits? CheckJC v7.4 attaches a per‑session
`data-value="<LETTER>"` to each button. The letter‑to‑digit mapping
is fixed for the whole session; only the **physical positions** of
the buttons reshuffle after every click. So the solver only has to
read the image once, and the scheduler does the rest by re‑reading
the DOM between clicks.

### Two solvers, same interface

| Solver | When it runs | Latency | Cost |
|---|---|---|---|
| `LLMVisionSolver` (Gemini) | User has `google_api_key` in profile | ~2 s | Free tier covers a typical 4 fichajes/day |
| `TelegramHumanSolver` | Always as fallback | as long as the user takes to reply (≤ 5 min) | Free |

The `HybridCaptchaSolver` chains them: try Gemini first; on any
failure (HTTP error, malformed reply, missing key) fall back to
Telegram automatically. This means existing users with Telegram
configured keep working exactly like before; users who add a Gemini
key get hands‑free fichaje.

Full design rationale lives in
[`docs/migrations/captcha-relay.md`](docs/migrations/captcha-relay.md)
and the original v7.4 migration is documented in
[`docs/migrations/checkjc-v7.4.md`](docs/migrations/checkjc-v7.4.md).

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (or a single Docker host that can
  run both).
- A Telegram bot token from [@BotFather](https://t.me/botfather) for
  notifications and the captcha relay.
- *(Optional)* A Google Gemini API key from
  [aistudio.google.com](https://aistudio.google.com/app/apikey) per
  user who wants hands‑free captcha solving.

### Configuration

1. **Create the environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** and fill in the required values:

   | Variable | Purpose |
   |---|---|
   | `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database |
   | `POSTGRES_DB_PORT` | External port for the DB (only needed if you connect from the host) |
   | `FLASK_SECRET_KEY` | Flask session signing key — generate a strong random string |
   | `ADMIN_PASSWORD` | Password for the auto‑provisioned `admin` user |
   | `ENCRYPTION_KEY` | Fernet key used to encrypt CheckJC passwords and Gemini API keys at rest |
   | `TELEGRAM_BOT_TOKEN` | From @BotFather |
   | `TELEGRAM_CHAT_ID` | Default chat ID for global / boot messages |
   | `WEB_PORT` / `PORT` | External / internal web port |
   | `CHECK_TIME_VERSION` | Tag of the prebuilt image to run (e.g. `1.9.6`) |
   | `USER_CHECK_STAGGER_SECONDS` | Default `60`. Seconds between consecutive users to dodge CheckJC's anti‑bot |
   | `CHECKJC_LITE_RETRIES` | Default `2`. Extra `/login` reload attempts when CheckJC serves the lite HTML |
   | `CHECKJC_LITE_RETRY_SECONDS` | Default `60`. Wait between those retries |

   The Gemini‑related settings are **per user**, configured from the
   web UI's profile page, not from `.env`.

### Installation

#### Local build (development)

```bash
docker-compose up --build -d
```

#### Prebuilt image (production)

Set `CHECK_TIME_VERSION` to the [latest release tag](https://github.com/Gonzalez8/checktime/releases)
in `.env` (or `stack.env` in Portainer), then:

```bash
docker compose pull app
docker compose up -d
```

Open `http://<your-host>:<WEB_PORT>`.

The first boot auto‑creates tables and applies any pending column
migrations (logged on startup). Log in with `admin` /
`$ADMIN_PASSWORD` and create your real user account.

---

## Usage

### Web Interface

1. **Login** with `admin` + `ADMIN_PASSWORD`.
2. **Register a real user** (recommended over using `admin` daily).
3. **Profile** tab → set up:
   - Account info and password.
   - **CheckJC credentials** (username, password, subdomain). Stored
     encrypted.
   - **Telegram chat ID** (use `/getchatid` in the bot to fetch
     yours).
   - *(Optional)* **Google API Key** + Gemini model dropdown. If
     left empty, the captcha is solved via Telegram instead.
4. **Schedules** → create one or more periods with weekday times.
5. **Holidays** → add manually, in bulk, or import an `.ics` file.
6. **Admin** menu (only `is_admin` users):
   - **Users**: list, reset password, delete users.
   - **Broadcast**: send a message to selected Telegram‑enabled users.

### Telegram Bot

- `/start` — welcome + command list.
- `/getchatid` — prints your chat ID, for the profile setup.
- `/addfestivo YYYY-MM-DD [Description]` — add a holiday.
- `/delfestivo YYYY-MM-DD` — remove a holiday.
- `/listfestivos` — list upcoming holidays.
- Reply to a captcha image with **16 digits** (`<10 keypad><6
  captcha>`) — the scheduler picks it up automatically. Used when no
  Gemini key is configured or as a fallback.

### Password recovery

- Login page → *Forgot password?* → enter username or email.
- If the user has Telegram configured, a one‑time reset link is sent
  there (no SMTP needed).
- If not, an admin can issue a one‑time temporary password from
  *Admin → Users → Reset password*.

---

## Deployment with the prebuilt image

CI publishes a tagged image to GitHub Container Registry on every
release tag (`vX.Y.Z`). The same image works for the standard and
Gluetun (VPN) compose flavours.

```bash
# Pick a release: https://github.com/Gonzalez8/checktime/releases
sed -i 's/^CHECK_TIME_VERSION=.*/CHECK_TIME_VERSION=1.9.6/' stack.env
docker compose pull app
docker compose up -d app
```

Two compose files are included:

- `docker-compose.yml` — standard deployment.
- `docker-compose.gluetun.yml` — routes the `app` container's egress
  through Gluetun + NordVPN so CheckJC sees a stable, known IP.

---

## Change history

Recent functionality, summarised. Each release has its own GitHub
release notes with full details and rationale.

| Version | What it added / fixed |
|---|---|
| **v1.9.6** | Default Gemini model `gemini-2.5-flash-lite`, `thinkingBudget=0` for compatibility with `gemini-2.5-flash`, bigger `maxOutputTokens` |
| v1.9.5 | Detect CheckJC per‑user account lockout banner; back off retries that contributed to bans |
| v1.9.4 | Extra Stencil hydration wait before submit on lite‑variant bodies *(retry portion reverted in 1.9.5)* |
| v1.9.3 | Hotfix: 500 on `/auth/profile` caused by duplicate `name=` kwarg on submit buttons |
| v1.9.2 | Bulletproof migrations: `information_schema` check + per‑statement transactions, diagnostic logging |
| v1.9.1 | Per‑user Gemini model dropdown; default moved to `2.5-flash`; fix migration transaction abort |
| **v1.9.0** | **Per‑user Google Gemini API key** in the profile. New `LLMVisionSolver` + `HybridCaptchaSolver` (LLM first, Telegram fallback) |
| v1.8.2 | Hotfix: scheduler app context for the captcha DB writes; plain‑text error notifications |
| v1.8.1 | Captcha solver asks for the **full 16 digits** (keypad + captcha) instead of relying on flaky Tesseract OCR |
| **v1.8.0** | **CheckJC verification captcha relay**: composite image shipped via Telegram, scheduler waits for the 6‑letter sequence and clicks |
| v1.7.4 | Detect lite‑variant DOM and retry without bailing on the first form‑not‑found |
| v1.7.3 | Retry on lite‑variant HTML; better diagnostics on `/login` failures |
| v1.7.2 | Stagger consecutive users in `schedule_check` to avoid the per‑IP anti‑bot |
| v1.7.1 | Delete users from the admin page; per‑recipient picker in the broadcast |
| **v1.7.0** | **Password recovery** via Telegram + admin fallback (one‑time temporary password) |
| v1.6.0 | Admin Telegram broadcast |
| v1.5.0 → v1.5.5 | Migration to Playwright + Chromium for CheckJC v7.4 |
| v1.4.0 | CheckJC subdomain configurable per user |
| v1.3.0 | Day overrides |
| v1.2.0 | Encrypted storage for CheckJC credentials |

Full release notes: <https://github.com/Gonzalez8/checktime/releases>

---

## Screenshots

**Home**
![Home](docs/screenshots/new-home.png)

**Dashboard**
![Dashboard](docs/screenshots/new-dashboard.png)

**Holidays**
![Holidays](docs/screenshots/new-holidays.png)

**Schedules**
![Schedules](docs/screenshots/new-schedules.png)

---

## License

This project is licensed under the **MIT License**. See the
[LICENSE](LICENSE) file for details.

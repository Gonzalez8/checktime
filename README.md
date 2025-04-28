# CheckTime

Automated check-in and check-out system for CheckJC with web management and Telegram integration.

---

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Architecture Overview](#architecture-overview)
- [Service Details](#service-details)
- [Multi-User Support](#multi-user-support)
- [Requirements](#requirements)
- [Installation](#installation)
  - [1. Configuration](#1-configuration)
  - [2. Installation with Docker (Recommended)](#2-installation-with-docker-recommended)
  - [3. Installation without Docker (Development)](#3-installation-without-docker-development)
- [Using the Web Interface](#using-the-web-interface)
- [License](#license)
- [Additional Notes](#additional-notes)

---

## Features

- Automatic check-in/check-out based on user schedules
- Holiday detection (national, regional, local)
- Multi-user support with personal CheckJC credentials
- Telegram bot integration for notifications and remote management
- Web dashboard for full configuration
- Support for custom schedules and holiday management

---

## Screenshots

### Dashboard Views
![Calendar View](docs/screenshots/dashboard-calendar.png)  
![Statistics View](docs/screenshots/dashboard-stats.png)

### Holiday and Schedule Management
![Holiday Import](docs/screenshots/holiday-import.png)  
![Schedule Editor](docs/screenshots/schedule-editor.png)

---

## Architecture Overview

CheckTime consists of four main services:
- **Web**: User dashboard and system management.
- **Scheduler**: Automated clock-in/clock-out execution.
- **Bot**: Telegram integration for notifications and commands.
- **Database**: PostgreSQL for persistent storage.

Each service runs independently but shares a single database for consistency.

---

## Service Details

- **Web Service**: Admin dashboard, user management, holiday import, schedule setup.
- **Scheduler Service**: Executes user check-ins/check-outs according to personalized calendars.
- **Telegram Bot**: Sends notifications and allows basic remote commands via Telegram.
- **Database**: Stores users, credentials, holidays, schedules, and preferences.

---

## Multi-User Support

Each user can:
- Register their own CheckJC credentials.
- Manage personal schedules and holidays.
- Set up Telegram notifications independently.
- Control automatic check-in/out settings.

All operations are fully isolated per user.

---

## Requirements

- **Python 3.8+**
- **Google Chrome** and **Chromedriver** (compatible version)
- **Docker** and **Docker Compose** (for production deployment)

---

## Installation

Before starting, **make sure you configure your environment variables**.

---

### 1. Configuration

1. **Create your `.env` file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file** with your preferred settings:
   - **Database Settings**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_DB_PORT`.
   - **Web App Settings**: `FLASK_SECRET_KEY`, `ADMIN_PASSWORD`, `PORT`, `WEB_PORT`.
   - **Telegram Bot Settings**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_BOT_NAME` (optional).
   - **Timezone and Logging**: `TZ`, `LOG_LEVEL`.

> **Important:**  
> The `.env` file is **mandatory**.  
> Without it, the application and Docker Compose will not start correctly.

---

### 2. Installation with Docker (Recommended)

1. **Build and start all services**:
   ```bash
   docker compose up -d
   ```

2. **Access the web interface**:
   Open your browser at:
   ```
   http://localhost:5001
   ```
   (or the port you set in `WEB_PORT`).

3. **Available Docker services**:
   You can start specific services manually if needed:
   ```bash
   docker compose up -d web        # Web dashboard
   docker compose up -d scheduler  # Scheduler service
   docker compose up -d bot        # Telegram bot
   docker compose up -d db         # Database only
   ```

4. **(First time)**  
   - Login with username `admin` and the password you set in `ADMIN_PASSWORD`.
   - Configure your own user account, schedules, holidays, and Telegram notifications.

---

### 3. Installation without Docker (Development Mode)

1. **Create a Python virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

3. **Run each service manually**:

   - Web interface:
     ```bash
     python -m src.checktime.web.server
     ```
   - Scheduler service:
     ```bash
     python -m src.checktime.scheduler.service
     ```
   - Telegram bot:
     ```bash
     python -m src.checktime.bot.listener
     ```

> ⚠️ Make sure your PostgreSQL database is already running if you work without Docker.

---

## Using the Web Interface

1. Access the web at `http://localhost:5001`.
2. Login as **admin** or register a new user.
3. Through the dashboard you can:
   - Manage user accounts
   - Import holidays from `.ics` files
   - Set check-in/check-out schedules
   - Configure Telegram notifications
   - Enable or disable automatic operations per user

---

## License

This project is licensed under the **MIT License**.  
Feel free to use, modify, and distribute it under the terms of the license.

---

## Additional Notes

- If you plan to use **Telegram**, make sure the bot token is correctly set in `.env`.
- For **Scheduler** to work, ensure your installed **Chromedriver** version matches your **Google Chrome** version.
- You can monitor logs with:
  ```bash
  docker compose logs -f
  ```
- Important logs are also stored in `logs/error.log`.

---
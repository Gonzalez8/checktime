# CheckTime

An application for automating check-in and check-out on the CheckJC system.

## Features

- Automated check-in and check-out on working days
- Automatic detection of weekends and holidays
- Support for multiple users with individual schedules and credentials
- User profiles with CheckJC credential management
- Personalized Telegram notifications for each user
- Web interface to configure schedules and holidays

## Screenshots

### Dashboard
![Dashboard Calendar View](docs/screenshots/dashboard-calendar.png)
The main dashboard displays a monthly calendar with daily check-in and check-out times.

![Dashboard Stats View](docs/screenshots/dashboard-stats.png)
The dashboard also shows current schedule, upcoming holidays, active schedule periods, and statistics.

### User Management
Users can manage their own CheckJC credentials and preferences through their profile page. 
This allows each user to configure their own check-in/check-out automation.

Each user can also set up their own Telegram notifications to receive alerts about their check-in/out operations.

### Holiday Management
![Holiday Import](docs/screenshots/holiday-import.png)
Easily import holidays from ICS calendar files.

### Schedule Management
![Schedule Editor](docs/screenshots/schedule-editor.png)
Edit daily schedules with an intuitive interface.

## Service Architecture

CheckTime is organized into three independent services, each with a single responsibility:

1. **Web Service**: Provides the web user interface for system administration
2. **Scheduler Service**: Performs automatic clock-in/clock-out according to configured schedules for all users
3. **Bot Service**: Handles Telegram integration for notifications and commands

All services connect to a PostgreSQL database for persistent storage of schedules, holidays, and configuration.

This separation ensures greater stability, maintainability, and scalability of the system.

## Services Explained

### Web Service
The web interface provides an intuitive dashboard for users to:
- View current configuration and system status
- Manage holidays (add individual days or date ranges)
- Configure schedule periods (e.g., summer schedule, winter schedule)
- Set check-in/check-out times for each day of the week
- Manage their CheckJC credentials securely
- Configure personal Telegram notifications
- Enable/disable automatic check-in/out for their account
- Update their profile information and password

### Scheduler Service
This service handles the automation of clock-in/clock-out actions:
- Supports multiple users with individual schedules and check-in/out times
- Runs according to the schedules configured in the web interface
- Uses separate threads for each user's check-in/out operations
- Automatically detects and skips weekends and holidays
- Uses a Chrome webdriver to interact with the CheckJC system
- Logs all actions for auditing and troubleshooting
- Sends personalized notifications to each user via Telegram

### Bot Service
The Telegram bot provides remote management capabilities:
- Allows holiday management directly from your phone
- Sends personalized notifications about check-in/check-out events
- Provides status updates about the system
- Allows administrators to add, remove, or list holidays remotely
- Supports individual user chat IDs for personalized notifications

### Database
Uses PostgreSQL to store:
- User accounts with securely encrypted passwords
- CheckJC credentials (stored securely for each user)
- Telegram configuration (chat ID and notification preferences)
- Holiday information (date and description)
- Schedule periods and their date ranges
- Daily check-in/check-out times for each schedule period
- User-specific preferences and settings

## Multi-User Support

CheckTime now supports multiple users, each with their own:
- CheckJC credentials (securely stored)
- Telegram notifications configuration
- Schedule periods and daily check-in/out times
- Holiday management
- Account preferences

The system ensures that each user's check-in/out operations are performed securely and independently, and notifications are sent accordingly.

## User Registration and Profile Management

### Registration
New users can:
- Create an account with a unique username and email
- Optionally configure their CheckJC credentials during registration
- Optionally configure their Telegram notifications during registration
- Enable or disable automatic check-in/out

### User Profile
Users can manage their profile including:
- Update personal information (username, email)
- Change their password securely
- Configure or update their CheckJC credentials
- Set up Telegram notifications with their personal chat ID
- Enable or disable automatic check-in/out

## Telegram Integration

CheckTime now supports personalized Telegram notifications for each user:

### Setting Up Telegram
1. Each user can set up their own Telegram chat ID in their profile
2. The system will send notifications only to users who have configured their Telegram settings
3. Users can enable or disable notifications at any time

### Automatic Notifications
The system sends personalized notifications for:
- Successful check-ins and check-outs
- Failed check-in/out attempts
- System status updates
- Important events like holidays and schedule changes

### Commands
The following commands are available in the Telegram bot:

- `/getchatid` - Get your Telegram chat ID for configuration
- `/addfestivo YYYY-MM-DD [description]` - Add a new holiday date with optional description
  Example: `/addfestivo 2023-12-25 Christmas Day`
- `/delfestivo YYYY-MM-DD` - Delete a holiday date
  Example: `/delfestivo 2023-12-25`
- `/listfestivos` - List upcoming holidays for the current year
  Shows dates, descriptions, and how many days until each holiday

## Requirements

- Python 3.8+
- Google Chrome
- ChromeDriver (compatible with your installed Chrome version)
- Docker and Docker Compose (recommended for deployment)

## Configuration

1. Copy the `.env.example` file to `.env` and configure the environment variables:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file with your configuration:

   ### Database Configuration
   ```
   # Path to store database files
   DB_STORAGE_PATH=./postgres_data
   
   # PostgreSQL credentials
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=checktime
   POSTGRES_DB_PORT=5432
   ```

   ### Web Server Configuration
   ```
   # Application version
   CHECK_TIME_VERSION=latest
   
   # Secret key for Flask sessions (change in production!)
   FLASK_SECRET_KEY=your_secure_random_key
   
   # Admin password for initial login
   ADMIN_PASSWORD=your_admin_password
   
   # Internal and external port configuration
   PORT=5000
   WEB_PORT=5001
   ```

   ### Telegram Configuration
   ```
   # Telegram bot token (from BotFather)
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   
   # Default admin Telegram chat ID
   TELEGRAM_CHAT_ID=your_admin_chat_id
   
   # Bot name
   TELEGRAM_BOT_NAME=name_of_your_bot
   ```

   ### Additional Settings
   ```
   # Timezone configuration
   TZ=Europe/Madrid
   
   # Logging level
   LOG_LEVEL=INFO
   ```

   Note: Individual user CheckJC credentials and Telegram chat IDs are stored in the database, not in environment variables.

## Installation and Execution

### With Docker Compose (recommended)

1. Build and run all services:
   ```
   docker compose up -d
   ```

2. Access the web interface at: http://localhost:5001 (or whatever port you configured as WEB_PORT)

3. To start specific services:
   ```
   docker compose up -d web       # Just the web interface
   docker compose up -d scheduler # Just the scheduler service
   docker compose up -d bot       # Just the Telegram bot
   docker compose up -d db        # Just the database
   ```

   Note: The database service automatically starts as a dependency when other services are started.

### Without Docker (Development)

1. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```

2. Run each service separately:
   ```
   # Web interface
   python -m src.checktime.web.server
   
   # Scheduler service
   python -m src.checktime.scheduler.service
   
   # Telegram bot
   python -m src.checktime.bot.listener
   ```

## Using the Web Interface

1. Access http://localhost:5001 (or whatever port you configured as WEB_PORT)
2. Log in with username `admin` and the password configured in `ADMIN_PASSWORD`
3. New users can register and configure their own CheckJC credentials and Telegram settings
4. From the dashboard you can:
   - View summary of current configuration
   - Manage holidays
   - Configure schedule periods
   - Set check-in/check-out times for each day of the week
5. From the user profile page, you can:
   - Update your account information
   - Configure your CheckJC credentials
   - Set up Telegram notifications
   - Enable or disable automatic check-in/out

## License

This project is licensed under the MIT License. 
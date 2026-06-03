from setuptools import setup, find_packages

setup(
    name="checktime",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "python-dotenv>=0.19.0",
        "requests>=2.26.0",
        "schedule>=1.1.0",
        # Drop-in de Playwright parcheado (rebrowser-patches): elimina el
        # leak de Runtime.enable por CDP que los anti-bot (Cloudflare,
        # DataDome, y al parecer el sensor de CheckJC/InfoJC) detectan para
        # identificar automatizacion. Mismo namespace de import "playwright".
        "rebrowser-playwright==1.52.0",
        "python-telegram-bot>=20.8",
        "flask>=2.3.3",
        "flask-sqlalchemy>=3.1.1",
        "flask-wtf>=1.2.1",
        "flask-login>=0.6.3",
        "email-validator>=2.1.0",
        "icalendar>=6.1.3",
        "psycopg2-binary>=2.9.9",
        "alembic>=1.13.1",
        "cryptography>=41.0.1",
        "gunicorn>=21.2.0",
        "Pillow>=10.0.0"
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "checktime-scheduler=checktime.scheduler.service:main",
            "checktime-bot=checktime.bot.listener:main",
            "checktime-web=checktime.web.server:main",
        ],
    },
) 
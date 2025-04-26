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
        "selenium>=4.1.0",
        "python-telegram-bot>=20.8",
        "chromedriver-autoinstaller>=0.6.4",
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
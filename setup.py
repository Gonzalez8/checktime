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
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "checktime-fichar=checktime.main:main",
            "checktime-bot=checktime.bot.main:main",
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="Sistema automatizado de fichaje con notificaciones por Telegram",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="fichaje, automation, telegram",
    project_urls={
        "Source": "<url-del-repositorio>",
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
        "Topic :: Office/Business",
    ],
) 
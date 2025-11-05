#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="backup-monitor",
    version="2.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A comprehensive backup monitoring system with multi-directory support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/backup-monitor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "backup-monitor=backup_monitor.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "backup_monitor": ["templates/*.html", "templates/*.txt"],
    },
)
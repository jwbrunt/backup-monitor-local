"""
Backup Monitor - A comprehensive backup monitoring system.

This package provides tools for monitoring backup directories, tracking file activity,
and generating reports with email notifications.
"""

__version__ = "2.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core.monitor import BackupMonitor
from .core.scanner import DirectoryScanner
from .reporters.email_reporter import EmailReporter

__all__ = ["BackupMonitor", "DirectoryScanner", "EmailReporter"]
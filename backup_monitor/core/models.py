"""Data models for backup monitoring."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class FileInfo:
    """Information about a file."""
    path: str
    name: str
    size: int
    modified_time: datetime
    is_directory: bool


@dataclass
class DirectoryStats:
    """Statistics about a directory."""
    path: str
    file_count: int
    subdirectory_count: int
    total_size: int
    most_recent_file: Optional[FileInfo]
    is_empty: bool
    error_message: Optional[str] = None
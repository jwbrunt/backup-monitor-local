"""Formatting utilities for backup monitor reports."""

from datetime import datetime, timedelta
from typing import Optional


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes.
        
    Returns:
        Human readable size string.
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes // (1024 * 1024)}MB"
    else:
        return f"{size_bytes // (1024 * 1024 * 1024)}GB"


def format_date(dt: datetime, short: bool = False) -> str:
    """Format datetime for display.
    
    Args:
        dt: Datetime to format.
        short: If True, use short format.
        
    Returns:
        Formatted date string.
    """
    if short:
        return dt.strftime('%Y-%m-%d %H:%M')
    else:
        return dt.strftime('%Y-%m-%d %H:%M:%S')


def get_activity_indicator(modified_time: Optional[datetime], use_emoji: bool = True) -> str:
    """Get activity indicator based on how recently a file was modified.
    
    Args:
        modified_time: When the file was last modified.
        use_emoji: Whether to use emoji indicators.
        
    Returns:
        Activity indicator string.
    """
    if modified_time is None:
        return "⚪ UNKNOWN" if use_emoji else "- UNK"
    
    now = datetime.now()
    time_diff = now - modified_time
    days_old = time_diff.days
    
    if use_emoji:
        if days_old == 0:
            return "📍 TODAY"
        elif days_old == 1:
            return "📅 YEST"
        elif days_old <= 7:
            return f"📆 {days_old}d"
        elif days_old <= 30:
            return f"📋 {days_old}d"
        else:
            return f"📁 {days_old}d"
    else:
        if days_old == 0:
            return "* TODAY"
        elif days_old == 1:
            return "* YEST"
        elif days_old <= 7:
            return f"+ {days_old}d"
        elif days_old <= 30:
            return f"- {days_old}d"
        else:
            return f"o {days_old}d"


def format_path_relative(full_path: str, base_path: str) -> str:
    """Format path relative to base path.
    
    Args:
        full_path: Full absolute path.
        base_path: Base path to make relative to.
        
    Returns:
        Relative path string.
    """
    if full_path.startswith(base_path):
        rel_path = full_path[len(base_path):].lstrip('/')
        return rel_path if rel_path else '.'
    return full_path


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length.
    
    Args:
        text: Text to truncate.
        max_length: Maximum length.
        suffix: Suffix to add when truncating.
        
    Returns:
        Truncated string.
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix
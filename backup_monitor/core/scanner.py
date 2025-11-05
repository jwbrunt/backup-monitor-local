"""Directory scanning functionality for backup monitoring."""

import os
import stat
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator, Tuple
from datetime import datetime
from .models import FileInfo, DirectoryStats


class DirectoryScanner:
    """Scans directories and collects file statistics."""
    
    def __init__(self, max_depth: int = 3, max_dirs: int = 200, 
                 file_size_limit_mb: int = 100, timeout_seconds: int = 300):
        """Initialize directory scanner.
        
        Args:
            max_depth: Maximum depth to scan directories.
            max_dirs: Maximum number of directories to scan.
            file_size_limit_mb: Skip files larger than this for detailed analysis.
            timeout_seconds: Timeout for scan operations.
        """
        self.max_depth = max_depth
        self.max_dirs = max_dirs
        self.file_size_limit = file_size_limit_mb * 1024 * 1024
        self.timeout_seconds = timeout_seconds
        self.logger = logging.getLogger(__name__)
        
    def scan_directory(self, base_path: str, exclude_patterns: List[str] = None) -> List[DirectoryStats]:
        """Scan a directory and return statistics.
        
        Args:
            base_path: Base path to scan.
            exclude_patterns: List of path patterns to exclude.
            
        Returns:
            List of DirectoryStats objects.
        """
        exclude_patterns = exclude_patterns or []
        results = []
        
        self.logger.info(f"Starting scan of {base_path}")
        
        try:
            results = self._scan_local_directory(base_path, exclude_patterns)
        except Exception as e:
            self.logger.error(f"Error scanning {base_path}: {e}")
            # Return empty result with error
            results = [DirectoryStats(
                path=base_path,
                file_count=0,
                subdirectory_count=0,
                total_size=0,
                most_recent_file=None,
                is_empty=True,
                error_message=str(e)
            )]
        
        self.logger.info(f"Completed scan of {base_path}, found {len(results)} directories")
        return results
    
    def _scan_local_directory(self, base_path: str, exclude_patterns: List[str]) -> List[DirectoryStats]:
        """Scan local directory."""
        results = []
        processed_count = 0
        
        # Get all directories to scan
        directories = self._get_directories_to_scan(base_path, exclude_patterns)
        
        for directory in directories:
            if processed_count >= self.max_dirs:
                self.logger.warning(f"Reached maximum directory limit ({self.max_dirs})")
                break
                
            try:
                stats = self._analyze_directory(directory, exclude_patterns)
                results.append(stats)
                processed_count += 1
                
                if processed_count % 50 == 0:
                    self.logger.info(f"Processed {processed_count} directories...")
                    
            except Exception as e:
                self.logger.error(f"Error analyzing directory {directory}: {e}")
                # Add error result
                results.append(DirectoryStats(
                    path=directory,
                    file_count=0,
                    subdirectory_count=0,
                    total_size=0,
                    most_recent_file=None,
                    is_empty=True,
                    error_message=str(e)
                ))
        
        return results
    
    def _get_directories_to_scan(self, base_path: str, exclude_patterns: List[str]) -> List[str]:
        """Get list of directories to scan."""
        directories = []
        
        if not os.path.exists(base_path):
            raise FileNotFoundError(f"Path does not exist: {base_path}")
        
        if not os.path.isdir(base_path):
            raise ValueError(f"Path is not a directory: {base_path}")
        
        # Use os.walk for efficient directory traversal
        for root, dirs, files in os.walk(base_path):
            # Calculate current depth
            depth = root[len(base_path):].count(os.sep)
            if depth >= self.max_depth:
                dirs[:] = []  # Don't recurse further
                continue
            
            # Check if this directory should be excluded
            if self._is_excluded(root, exclude_patterns):
                dirs[:] = []  # Don't recurse into excluded directories
                continue
            
            # Skip the root directory itself (e.g., /backup) to avoid empty entries
            # Only include subdirectories
            if root != base_path:
                directories.append(root)
            
            # Limit the number of directories we collect
            if len(directories) >= self.max_dirs * 2:  # Buffer for filtering
                break
        
        return directories[:self.max_dirs]
    
    def _is_excluded(self, path: str, exclude_patterns: List[str]) -> bool:
        """Check if a path should be excluded."""
        for pattern in exclude_patterns:
            if path.startswith(pattern):
                return True
        return False
    
    def _analyze_directory(self, directory_path: str, exclude_patterns: List[str] = None) -> DirectoryStats:
        """Analyze a single directory with enhanced recency detection.
        
        Now considers both files AND subdirectories for recency detection.
        This provides better visibility into recently created/modified directories.
        Optionally excludes specific files based on exclude_patterns.
        """
        exclude_patterns = exclude_patterns or []
        file_count = 0
        subdirectory_count = 0
        total_size = 0
        most_recent_file = None
        most_recent_time = None
        
        try:
            # Check if directory is readable
            if not os.access(directory_path, os.R_OK):
                return DirectoryStats(
                    path=directory_path,
                    file_count=0,
                    subdirectory_count=0,
                    total_size=0,
                    most_recent_file=None,
                    is_empty=True,
                    error_message="Directory not readable"
                )
            
            # Scan immediate contents (non-recursive for this level)
            for entry in os.scandir(directory_path):
                try:
                    entry_stat = entry.stat()
                    
                    if entry.is_file(follow_symlinks=False):
                        # Skip excluded files
                        if self._is_excluded(entry.path, exclude_patterns):
                            continue
                            
                        file_count += 1
                        file_size = entry_stat.st_size
                        total_size += file_size
                        
                        # Track most recent file regardless of size (we don't read contents)
                        modified_time = datetime.fromtimestamp(entry_stat.st_mtime)
                        if most_recent_time is None or modified_time > most_recent_time:
                            most_recent_time = modified_time
                            most_recent_file = FileInfo(
                                path=entry.path,
                                name=entry.name,
                                size=file_size,
                                modified_time=modified_time,
                                is_directory=False
                            )
                    
                    elif entry.is_dir(follow_symlinks=False):
                        subdirectory_count += 1
                        
                        # ENHANCED: Also check subdirectory modification time
                        # This helps detect recently created/modified directories
                        dir_modified_time = datetime.fromtimestamp(entry_stat.st_mtime)
                        if most_recent_time is None or dir_modified_time > most_recent_time:
                            most_recent_time = dir_modified_time
                            most_recent_file = FileInfo(
                                path=entry.path,
                                name=entry.name,
                                size=0,  # Directories don't have file size
                                modified_time=dir_modified_time,
                                is_directory=True  # Mark as directory
                            )
                
                except (OSError, ValueError) as e:
                    # Skip files/directories that can't be accessed
                    self.logger.debug(f"Skipping {entry.path}: {e}")
                    continue
        
        except (OSError, ValueError) as e:
            return DirectoryStats(
                path=directory_path,
                file_count=0,
                subdirectory_count=0,
                total_size=0,
                most_recent_file=None,
                is_empty=True,
                error_message=str(e)
            )
        
        return DirectoryStats(
            path=directory_path,
            file_count=file_count,
            subdirectory_count=subdirectory_count,
            total_size=total_size,
            most_recent_file=most_recent_file,
            is_empty=(file_count == 0)
        )

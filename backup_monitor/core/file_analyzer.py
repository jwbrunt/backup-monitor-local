"""File analyzer for processing backup scan results."""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
from .models import DirectoryStats


class FileAnalyzer:
    """Analyzes backup scan results and generates statistics."""
    
    def __init__(self, days_back: int = 7):
        """Initialize file analyzer.
        
        Args:
            days_back: Number of days to consider for recent activity.
        """
        self.days_back = days_back
        self.logger = logging.getLogger(__name__)
    
    def analyze_results(self, scan_results: Dict[str, List[DirectoryStats]]) -> Dict[str, Any]:
        """Analyze scan results and generate statistics.
        
        Args:
            scan_results: Results from backup scanning.
            
        Returns:
            Dictionary containing analysis results.
        """
        self.logger.info("Analyzing scan results")
        
        # Initialize counters
        total_locations = len(scan_results)
        total_directories = 0
        total_files = 0
        total_size = 0
        empty_directories = 0
        error_directories = 0
        recent_files = 0
        recent_activity = []
        
        # Calculate cutoff time for recent activity
        cutoff_time = datetime.now() - timedelta(days=self.days_back)
        
        # Process each location
        for location_name, location_stats in scan_results.items():
            for stats in location_stats:
                total_directories += 1
                
                # Count errors
                if stats.error_message:
                    error_directories += 1
                    continue
                
                # Count files and directories
                total_files += stats.file_count
                total_size += stats.total_size
                
                # Count empty directories
                if stats.is_empty:
                    empty_directories += 1
                
                # Check for recent activity
                if stats.most_recent_file and stats.most_recent_file.modified_time >= cutoff_time:
                    recent_files += 1
                    recent_activity.append({
                        'location': location_name,
                        'directory': stats.path,
                        'file': stats.most_recent_file.name,
                        'size': stats.most_recent_file.size,
                        'modified': stats.most_recent_file.modified_time,
                        'modified_str': stats.most_recent_file.modified_time.strftime('%Y-%m-%d %H:%M')
                    })
        
        # Sort recent activity by modification time (newest first)
        recent_activity.sort(key=lambda x: x['modified'], reverse=True)
        
        # Calculate percentages
        healthy_directories = total_directories - empty_directories - error_directories
        health_percentage = (healthy_directories / total_directories * 100) if total_directories > 0 else 0
        
        analysis = {
            'total_locations': total_locations,
            'total_directories': total_directories,
            'total_files': total_files,
            'total_size': total_size,
            'empty_directories': empty_directories,
            'error_directories': error_directories,
            'healthy_directories': healthy_directories,
            'health_percentage': health_percentage,
            'recent_files': recent_files,
            'recent_activity': recent_activity,
            'analysis_time': datetime.now(),
            'days_analyzed': self.days_back
        }
        
        self.logger.info(f"Analysis complete: {total_directories} directories, "
                        f"{total_files} files, {recent_files} recent files")
        
        return analysis
    
    def get_location_summary(self, location_stats: List[DirectoryStats]) -> Dict[str, Any]:
        """Get summary statistics for a single location.
        
        Args:
            location_stats: Directory statistics for one location.
            
        Returns:
            Summary statistics dictionary.
        """
        if not location_stats:
            return {
                'directories': 0,
                'files': 0,
                'total_size': 0,
                'empty_directories': 0,
                'error_directories': 0,
                'recent_files': 0,
                'most_recent_activity': None
            }
        
        total_directories = len(location_stats)
        total_files = sum(stats.file_count for stats in location_stats if not stats.error_message)
        total_size = sum(stats.total_size for stats in location_stats if not stats.error_message)
        empty_directories = sum(1 for stats in location_stats if stats.is_empty and not stats.error_message)
        error_directories = sum(1 for stats in location_stats if stats.error_message)
        
        # Find recent files and most recent activity
        cutoff_time = datetime.now() - timedelta(days=self.days_back)
        recent_files = 0
        most_recent_activity = None
        most_recent_time = None
        
        for stats in location_stats:
            if stats.error_message or not stats.most_recent_file:
                continue
                
            if stats.most_recent_file.modified_time >= cutoff_time:
                recent_files += 1
            
            if (most_recent_time is None or 
                stats.most_recent_file.modified_time > most_recent_time):
                most_recent_time = stats.most_recent_file.modified_time
                most_recent_activity = {
                    'directory': stats.path,
                    'file': stats.most_recent_file.name,
                    'size': stats.most_recent_file.size,
                    'modified': stats.most_recent_file.modified_time
                }
        
        return {
            'directories': total_directories,
            'files': total_files,
            'total_size': total_size,
            'empty_directories': empty_directories,
            'error_directories': error_directories,
            'recent_files': recent_files,
            'most_recent_activity': most_recent_activity
        }
    
    def identify_issues(self, scan_results: Dict[str, List[DirectoryStats]]) -> List[Dict[str, Any]]:
        """Identify potential issues in the backup data.
        
        Args:
            scan_results: Results from backup scanning.
            
        Returns:
            List of identified issues.
        """
        issues = []
        
        # Check for locations with no activity
        cutoff_time = datetime.now() - timedelta(days=self.days_back * 2)  # Extended period for issues
        
        for location_name, location_stats in scan_results.items():
            if not location_stats:
                issues.append({
                    'type': 'no_data',
                    'severity': 'high',
                    'location': location_name,
                    'message': 'No directories found or scan failed'
                })
                continue
            
            # Check for error directories
            error_count = sum(1 for stats in location_stats if stats.error_message)
            if error_count > 0:
                issues.append({
                    'type': 'access_errors',
                    'severity': 'medium',
                    'location': location_name,
                    'count': error_count,
                    'message': f'{error_count} directories could not be accessed'
                })
            
            # Check for locations with no recent activity
            has_recent_activity = False
            for stats in location_stats:
                if (not stats.error_message and stats.most_recent_file and 
                    stats.most_recent_file.modified_time >= cutoff_time):
                    has_recent_activity = True
                    break
            
            if not has_recent_activity:
                issues.append({
                    'type': 'stale_backup',
                    'severity': 'medium',
                    'location': location_name,
                    'message': f'No activity in the last {self.days_back * 2} days'
                })
            
            # Check for locations with high percentage of empty directories
            non_error_dirs = [s for s in location_stats if not s.error_message]
            if non_error_dirs:
                empty_percentage = sum(1 for s in non_error_dirs if s.is_empty) / len(non_error_dirs)
                if empty_percentage > 0.5:  # More than 50% empty
                    issues.append({
                        'type': 'many_empty_dirs',
                        'severity': 'low',
                        'location': location_name,
                        'percentage': empty_percentage * 100,
                        'message': f'{empty_percentage*100:.1f}% of directories are empty'
                    })
        
        return issues
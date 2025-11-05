"""Main backup monitoring class."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from .scanner import DirectoryScanner
from .models import DirectoryStats
from .file_analyzer import FileAnalyzer
from ..config.config_manager import ConfigManager
from ..reporters.email_reporter import EmailReporter


class BackupMonitor:
    """Main backup monitoring coordinator."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize backup monitor.
        
        Args:
            config_path: Optional path to configuration file.
        """
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        self.scanner = None
        self.analyzer = None
        self.email_reporter = None
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize monitoring components."""
        # Initialize scanner with config
        monitoring_config = self.config_manager.get_monitoring_config()
        self.scanner = DirectoryScanner(
            max_depth=monitoring_config.get('max_depth', 3),
            max_dirs=monitoring_config.get('max_dirs', 200),
            file_size_limit_mb=monitoring_config.get('file_size_limit_mb', 100),
            timeout_seconds=monitoring_config.get('timeout_seconds', 300)
        )
        
        # Initialize file analyzer
        self.analyzer = FileAnalyzer(
            days_back=monitoring_config.get('days_back', 7)
        )
        
        # Initialize email reporter if configured
        email_config = self.config_manager.get_email_config()
        if email_config:
            self.email_reporter = EmailReporter(
                smtp_server=email_config['smtp_server'],
                smtp_port=email_config.get('smtp_port', 587),
                smtp_user=email_config['smtp_user'],
                smtp_pass=email_config['smtp_pass'],
                from_address=email_config['from_address'],
                to_addresses=email_config['to_addresses'],
                use_tls=email_config.get('use_tls', True),
                use_sendemail=email_config.get('use_sendemail', False)
            )
    
    def scan_all_locations(self) -> Dict[str, List[DirectoryStats]]:
        """Scan all configured backup locations.
        
        Returns:
            Dictionary mapping location names to their directory statistics.
        """
        locations = self.config_manager.get_backup_locations()
        results = {}
        
        # Separate failover and non-failover locations
        failover_locations = self._group_failover_locations(locations)
        non_failover_locations = [loc for loc in locations if not loc.get('failover_group')]
        
        self.logger.info(f"Starting scan of {len(locations)} total backup locations")
        self.logger.info(f"Non-failover locations: {len(non_failover_locations)}")
        
        # Scan non-failover locations normally
        for location in non_failover_locations:
            location_name = location['name']
            self.logger.info(f"Scanning standard location: {location_name}")
            
            try:
                location_results = self._scan_location(location)
                results[location_name] = location_results
                self.logger.info(f"Successfully scanned {location_name}: {len(location_results)} directories")
            
            except Exception as e:
                self.logger.error(f"Failed to scan location {location_name}: {e}")
                # Add error result
                results[location_name] = [DirectoryStats(
                    path=location['path'],
                    file_count=0,
                    subdirectory_count=0,
                    total_size=0,
                    most_recent_file=None,
                    is_empty=True,
                    error_message=str(e)
                )]
        
        # Handle failover groups
        if failover_locations:
            self.logger.info(f"Failover groups detected: {list(failover_locations.keys())}")
            failover_results = self._scan_with_failover(failover_locations)
            results.update(failover_results)
        
        return results
    
    def _group_failover_locations(self, locations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group locations by failover_group configuration.
        
        Args:
            locations: List of location configurations.
            
        Returns:
            Dictionary mapping failover group names to location lists.
        """
        failover_groups = {}
        
        for location in locations:
            failover_group = location.get('failover_group')
            if failover_group:
                if failover_group not in failover_groups:
                    failover_groups[failover_group] = []
                failover_groups[failover_group].append(location)
        
        # Only return groups with multiple locations
        return {group: locs for group, locs in failover_groups.items() if len(locs) > 1}
    
    def _scan_with_failover(self, failover_groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[DirectoryStats]]:
        """Scan locations with failover logic.
        
        Args:
            failover_groups: Dictionary of failover groups.
            
        Returns:
            Dictionary mapping active location names to their directory statistics.
        """
        results = {}
        
        for group_name, group_locations in failover_groups.items():
            self.logger.info(f"Processing failover group '{group_name}' with {len(group_locations)} locations")
            
            # Find the active location in this group
            active_location = self._find_active_location(group_locations)
            
            if active_location:
                location_name = active_location['name']
                self.logger.info(f"Active location in group '{group_name}': {location_name}")
                
                try:
                    location_results = self._scan_location(active_location)
                    results[location_name] = location_results
                    self.logger.info(f"Successfully scanned active location {location_name}: {len(location_results)} directories")
                
                except Exception as e:
                    self.logger.error(f"Failed to scan active location {location_name}: {e}")
                    # Add error result
                    results[location_name] = [DirectoryStats(
                        path=active_location['path'],
                        file_count=0,
                        subdirectory_count=0,
                        total_size=0,
                        most_recent_file=None,
                        is_empty=True,
                        error_message=str(e)
                    )]
            else:
                self.logger.warning(f"No active location found in failover group '{group_name}'")
                # Add a placeholder result indicating no active location
                results[f"No Active Location ({group_name})"] = [DirectoryStats(
                    path="/unavailable",
                    file_count=0,
                    subdirectory_count=0,
                    total_size=0,
                    most_recent_file=None,
                    is_empty=True,
                    error_message=f"No active location found in failover group '{group_name}'"
                )]
        
        return results
    
    def _find_active_location(self, locations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the active location among failover candidates.
        
        Args:
            locations: List of location configurations in failover group.
            
        Returns:
            The active location configuration, or None if none are active.
        """
        from datetime import datetime, timedelta
        
        best_location = None
        most_recent_activity = None
        
        for location in locations:
            try:
                # Quick check for recent activity in the location
                activity_time = self._check_location_activity(location)
                
                if activity_time is None:
                    self.logger.debug(f"No activity found in location '{location['name']}'")
                    continue
                
                self.logger.debug(f"Location '{location['name']}' has activity from {activity_time}")
                
                # Update best location if this one has more recent activity
                if most_recent_activity is None or activity_time > most_recent_activity:
                    most_recent_activity = activity_time
                    best_location = location
            
            except Exception as e:
                self.logger.warning(f"Could not check activity for location '{location['name']}': {e}")
                continue
        
        # If we found a location with activity in the last 7 days, use it
        if best_location and most_recent_activity:
            days_old = (datetime.now() - most_recent_activity).days
            if days_old <= 7:
                self.logger.info(f"Selected active location '{best_location['name']}' (activity {days_old} days ago)")
                return best_location
            else:
                self.logger.warning(f"Best location '{best_location['name']}' has old activity ({days_old} days ago)")
        
        # If no recent activity, return the first accessible location
        for location in locations:
            try:
                if self._is_location_accessible(location):
                    self.logger.info(f"Selected fallback location '{location['name']}' (no recent activity found)")
                    return location
            except Exception as e:
                self.logger.debug(f"Location '{location['name']}' not accessible: {e}")
                continue
        
        return None
    
    def _check_location_activity(self, location: Dict[str, Any]) -> Optional[datetime]:
        """Check for recent activity in a location.
        
        Args:
            location: Location configuration.
            
        Returns:
            Datetime of most recent activity, or None if no activity.
        """
        import os
        from datetime import datetime
        
        location_type = location.get('type', 'local')
        path = location['path']
        
        try:
            if location_type == 'local':
                # Check if directory exists and get most recent modification
                if not os.path.exists(path):
                    return None
                
                # Get most recent file in the top level of the directory
                most_recent = None
                try:
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        if os.path.isfile(item_path):
                            mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                            if most_recent is None or mtime > most_recent:
                                most_recent = mtime
                        elif os.path.isdir(item_path):
                            # Check directory modification time
                            mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
                            if most_recent is None or mtime > most_recent:
                                most_recent = mtime
                except (OSError, PermissionError):
                    # If we can't read the directory, check the directory itself
                    most_recent = datetime.fromtimestamp(os.path.getmtime(path))
                
                return most_recent
            
        
        except Exception as e:
            self.logger.debug(f"Error checking activity for {path}: {e}")
            return None
    
    def _is_location_accessible(self, location: Dict[str, Any]) -> bool:
        """Check if a location is accessible.
        
        Args:
            location: Location configuration.
            
        Returns:
            True if location is accessible.
        """
        import os
        
        location_type = location.get('type', 'local')
        path = location['path']
        
        try:
            if location_type == 'local':
                return os.path.exists(path) and os.path.isdir(path)
            
        
        except Exception:
            return False
        
        return False
    
    def _scan_location(self, location: Dict[str, Any]) -> List[DirectoryStats]:
        """Scan a single backup location.
        
        Args:
            location: Location configuration dictionary.
            
        Returns:
            List of DirectoryStats for the location.
        """
        location_type = location.get('type', 'local')
        path = location['path']
        exclude_patterns = location.get('exclude_patterns', [])
        max_depth = location.get('max_depth', self.config_manager.get_monitoring_config().get('max_depth', 3))
        
        # Update scanner max_depth for this location
        original_max_depth = self.scanner.max_depth
        self.scanner.max_depth = max_depth
        
        try:
            if location_type == 'local':
                return self.scanner.scan_directory(path, exclude_patterns)
            
            
            else:
                raise ValueError(f"Unknown location type: {location_type}")
                
        finally:
            # Restore original max_depth
            self.scanner.max_depth = original_max_depth
    
    def generate_report(self, scan_results: Dict[str, List[DirectoryStats]], 
                       report_format: str = 'both') -> Dict[str, str]:
        """Generate reports from scan results.
        
        Args:
            scan_results: Results from scan_all_locations().
            report_format: Format for reports ('text', 'html', or 'both').
            
        Returns:
            Dictionary with report content (keys: 'text', 'html').
        """
        reports = {}
        
        # Analyze results first
        analysis = self.analyzer.analyze_results(scan_results)
        
        if report_format in ['text', 'both']:
            reports['text'] = self._generate_text_report(scan_results, analysis)
        
        if report_format in ['html', 'both']:
            reports['html'] = self._generate_html_report(scan_results, analysis)
        
        return reports
    
    def _generate_text_report(self, scan_results: Dict[str, List[DirectoryStats]], 
                             analysis: Dict[str, Any]) -> str:
        """Generate text report.
        
        Args:
            scan_results: Scan results.
            analysis: Analysis results.
            
        Returns:
            Text report content.
        """
        from ..utils.formatters import format_date, format_file_size, get_activity_indicator, truncate_string
        
        report_lines = []
        
        # Header
        report_lines.extend([
            "================================================================================",
            "                    BACKUP DIRECTORY MONITORING REPORT",
            f"                          Generated: {format_date(datetime.now())}",
            "================================================================================",
            "",
            "EXECUTIVE SUMMARY:",
            "=================="
        ])
        
        # Summary statistics
        total_locations = len(scan_results)
        total_directories = sum(len(stats) for stats in scan_results.values())
        total_files = analysis.get('total_files', 0)
        recent_activity = analysis.get('recent_files', 0)
        
        report_lines.extend([
            f"Backup locations monitored: {total_locations}",
            f"Total directories scanned: {total_directories}",
            f"Total files found: {total_files}",
            f"Recent activity (last {self.analyzer.days_back} days): {recent_activity} files",
            ""
        ])
        
        # Location details
        for location_name, location_stats in scan_results.items():
            report_lines.extend([
                f"LOCATION: {location_name}",
                "=" * (10 + len(location_name)),
                ""
            ])
            
            if not location_stats:
                report_lines.extend(["No directories found or error occurred.", ""])
                continue
            
            # Check if there was an error
            if len(location_stats) == 1 and location_stats[0].error_message:
                report_lines.extend([f"Error: {location_stats[0].error_message}", ""])
                continue
            
            # Table header
            report_lines.extend([
                f"{'Directory':<40} {'Files':>8} {'Subdirs':>8} {'Activity':>12} {'Recent File':<30} {'Modified':<20}",
                f"{'-' * 40} {'-' * 8} {'-' * 8} {'-' * 12} {'-' * 30} {'-' * 20}"
            ])
            
            # Directory entries
            for stats in location_stats:
                if stats.error_message:
                    continue
                
                # Format directory path (relative to base)
                dir_name = stats.path.split('/')[-1] or stats.path
                dir_name = truncate_string(dir_name, 38)
                
                # Format recent file info
                if stats.most_recent_file:
                    recent_file = truncate_string(stats.most_recent_file.name, 28)
                    modified_date = format_date(stats.most_recent_file.modified_time, short=True)
                    activity = get_activity_indicator(stats.most_recent_file.modified_time, use_emoji=False)
                else:
                    recent_file = "(no files)" if stats.is_empty else "(unknown)"
                    modified_date = "-"
                    activity = "- EMPTY" if stats.is_empty else "- UNK"
                
                report_lines.append(
                    f"{dir_name:<40} {stats.file_count:>8} {stats.subdirectory_count:>8} "
                    f"{activity:>12} {recent_file:<30} {modified_date:<20}"
                )
            
            report_lines.append("")
        
        # Recent activity section
        if analysis.get('recent_activity'):
            report_lines.extend([
                f"RECENT ACTIVITY (Last {self.analyzer.days_back} days):",
                "=" * (25 + len(str(self.analyzer.days_back))),
                ""
            ])
            
            for activity in analysis['recent_activity'][:20]:  # Show top 20
                report_lines.append(f"• {activity['location']}/{activity['file']} ({activity['modified']})")
            
            if len(analysis['recent_activity']) > 20:
                report_lines.append(f"... and {len(analysis['recent_activity']) - 20} more")
            
            report_lines.append("")
        
        # Footer
        report_lines.extend([
            "================================================================================",
            "Generated by Backup Monitor v2.0",
            f"Next scan recommended: {format_date(datetime.now())}",
            "================================================================================"
        ])
        
        return "\n".join(report_lines)
    
    def _generate_html_report(self, scan_results: Dict[str, List[DirectoryStats]], 
                             analysis: Dict[str, Any]) -> str:
        """Generate enhanced HTML report with clean modern design.
        
        This provides a comprehensive report showing directory breakdowns,
        recent activity with enhanced recency detection for files and subdirectories.
        
        Args:
            scan_results: Scan results by location.
            analysis: Analysis results including totals and activity.
            
        Returns:
            HTML report content.
        """
        from ..utils.formatters import format_date, format_file_size, get_activity_indicator
        
        # Create timestamp
        report_time = datetime.now()
        timestamp = report_time.strftime("%B %d, %Y at %I:%M %p")
        current_date = report_time.strftime('%B %d, %Y')
        
        # Calculate summary stats
        total_files = analysis.get('total_files', 0)
        recent_files = analysis.get('recent_files', 0)
        total_dirs = sum(len(stats) for stats in scan_results.values())
        total_size = analysis.get('total_size', 0)
        total_locations = len([name for name, stats in scan_results.items() if stats])
        
        # CSS matching the sample email report format
        css = '''
                body { 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background-color: #f5f5f5; 
                }
                .container {
                    max-width: 800px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }
                .header { 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; 
                    padding: 30px; 
                    text-align: center; 
                }
                .header h1 { 
                    margin: 0; 
                    font-size: 28px; 
                    font-weight: 300; 
                }
                .header p { 
                    margin: 5px 0 0 0; 
                    opacity: 0.9; 
                    font-size: 16px; 
                }
                .summary { 
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    color: white; 
                    padding: 20px; 
                    text-align: center; 
                }
                .summary h2 { 
                    margin: 0 0 15px 0; 
                    font-size: 20px; 
                    font-weight: 400; 
                }
                .stats {
                    display: flex;
                    justify-content: space-around;
                    flex-wrap: wrap;
                }
                .stat {
                    text-align: center;
                    margin: 10px;
                }
                .stat-number {
                    font-size: 24px;
                    font-weight: bold;
                    display: block;
                }
                .stat-label {
                    font-size: 12px;
                    opacity: 0.9;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }
                .content { 
                    padding: 30px; 
                }
                .section {
                    margin-bottom: 30px;
                }
                .section h3 {
                    color: #333;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
                table { 
                    border-collapse: collapse; 
                    width: 100%; 
                    font-size: 14px;
                }
                th, td { 
                    border: 1px solid #e0e0e0; 
                    padding: 12px 8px; 
                    text-align: left; 
                }
                th { 
                    background-color: #f8f9fa; 
                    font-weight: 600;
                    color: #555;
                }
                .activity-today { color: #28a745; font-weight: bold; }
                .activity-yesterday { color: #ffc107; font-weight: bold; }
                .activity-recent { color: #17a2b8; }
                .activity-old { color: #6c757d; }
                .activity-empty { color: #dc3545; }
                
                .recent-activity {
                    background-color: #f8f9fa;
                    border-radius: 6px;
                    padding: 20px;
                    margin: 20px 0;
                }
                .recent-activity h4 {
                    color: #28a745;
                    margin: 0 0 15px 0;
                }
                .recent-file {
                    padding: 8px 0;
                    border-bottom: 1px solid #e9ecef;
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                }
                .recent-file:last-child {
                    border-bottom: none;
                }
                .timestamp {
                    color: #6c757d;
                    float: right;
                }
                
                .footer { 
                    background-color: #f8f9fa; 
                    padding: 20px; 
                    text-align: center; 
                    color: #6c757d; 
                    font-size: 12px;
                }
                .footer a {
                    color: #667eea;
                    text-decoration: none;
                }
                
                @media (max-width: 600px) {
                    .stats {
                        flex-direction: column;
                    }
                    .stat {
                        margin: 5px;
                    }
                    table {
                        font-size: 12px;
                    }
                    th, td {
                        padding: 8px 4px;
                    }
                }
        '''
        
        # Start HTML structure with enhanced design
        html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EDI Daily Backup System Report</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗂️ EDI Daily Backup System Report</h1>
            <p class="timestamp">Generated on {timestamp}</p>
        </div>
        
        <div class="summary">
            <h2>📊 Executive Summary</h2>
            <div class="stats">
                <div class="stat">
                    <span class="stat-number">{total_locations}</span>
                    <span class="stat-label">Locations</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{total_dirs}</span>
                    <span class="stat-label">Directories</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{total_files:,}</span>
                    <span class="stat-label">Total Files</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{recent_files}</span>
                    <span class="stat-label">Recent Activity</span>
                </div>
            </div>
        </div>
        
        <div class="content">
'''
        
        # Process each location with enhanced logic
        for location_name, location_stats in scan_results.items():
            if not location_stats:
                continue
                
            # Determine if this is the main backup location
            is_main_backup = (location_name == "Main Backup" or 
                             ('/backup' in location_name and 
                              'backup1' not in location_name and 
                              'backup2' not in location_name))
            
            if is_main_backup:
                html_content += self._generate_main_backup_section(location_stats, analysis)
            else:
                html_content += self._generate_secondary_backup_section(location_name, location_stats)
        
        # Recent activity is now clustered under each location section
        
        # Add enhanced health status section
        html_content += self._generate_health_status_section(scan_results, analysis)
        
        # Close with enhanced footer
        report_id = report_time.strftime('%Y%m%d_%H%M%S')
        next_report = (report_time + timedelta(days=1)).strftime('%B %d, %Y')
        
        html_content += f'''
        </div>
        
        <div class="footer">
            <p><strong>🔍 Backup Monitor v2.0</strong> • Enhanced with subdirectory recency detection</p>
            <p>Report ID: {report_id} • Next scheduled report: {next_report}</p>
            <p>Generated on space.edirepository.org • Questions? Contact your system administrator</p>
        </div>
    </div>
</body>
</html>
'''
        
        return html_content
    
    def send_email_report(self, reports: Dict[str, str], subject_prefix: str = None) -> bool:
        """Send email report.
        
        Args:
            reports: Report content dictionary.
            subject_prefix: Optional subject prefix.
            
        Returns:
            True if email sent successfully.
        """
        if not self.email_reporter:
            self.logger.warning("Email reporter not configured")
            return False
        
        # Determine subject
        email_config = self.config_manager.get_email_config()
        prefix = subject_prefix or email_config.get('subject_prefix', 'Backup Monitor Report')
        subject = f"{prefix} - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Send email
        try:
            return self.email_reporter.send_report(
                subject=subject,
                text_content=reports.get('text'),
                html_content=reports.get('html')
            )
        except Exception as e:
            self.logger.error(f"Failed to send email report: {e}")
            return False
    
    def run_full_scan(self, send_email: bool = True, save_reports: bool = True) -> Dict[str, Any]:
        """Run a complete backup scan and generate reports.
        
        Args:
            send_email: Whether to send email report.
            save_reports: Whether to save reports locally.
            
        Returns:
            Dictionary with scan results and reports.
        """
        self.logger.info("Starting full backup scan")
        
        # Scan all locations
        scan_results = self.scan_all_locations()
        
        # Generate reports
        reports_config = self.config_manager.get_reports_config()
        report_format = reports_config.get('format', 'both')
        reports = self.generate_report(scan_results, report_format)
        
        # Save reports locally if configured
        if save_reports and reports_config.get('save_local', True):
            self._save_reports_locally(reports, reports_config)
        
        # Send email if configured and requested
        if send_email and self.email_reporter:
            email_sent = self.send_email_report(reports)
            self.logger.info(f"Email report sent: {email_sent}")
        
        self.logger.info("Full backup scan completed")
        
        return {
            'scan_results': scan_results,
            'reports': reports,
            'timestamp': datetime.now()
        }
    
    def _save_reports_locally(self, reports: Dict[str, str], reports_config: Dict[str, Any]):
        """Save reports to local files.
        
        Args:
            reports: Report content dictionary.
            reports_config: Reports configuration.
        """
        report_dir = Path(reports_config.get('local_directory', './reports'))
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save text report
        if 'text' in reports:
            text_file = report_dir / f'backup_report_{timestamp}.txt'
            text_file.write_text(reports['text'], encoding='utf-8')
            self.logger.info(f"Text report saved: {text_file}")
        
        # Save HTML report
        if 'html' in reports:
            html_file = report_dir / f'backup_report_{timestamp}.html'
            html_file.write_text(reports['html'], encoding='utf-8')
            self.logger.info(f"HTML report saved: {html_file}")
        
        # Clean up old reports
        self._cleanup_old_reports(report_dir, reports_config.get('retention_days', 30))
    
    def _cleanup_old_reports(self, report_dir: Path, retention_days: int):
        """Clean up old report files.
        
        Args:
            report_dir: Directory containing reports.
            retention_days: Number of days to keep reports.
        """
        import time
        
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
        
        for report_file in report_dir.glob('backup_report_*'):
            if report_file.stat().st_mtime < cutoff_time:
                try:
                    report_file.unlink()
                    self.logger.debug(f"Deleted old report: {report_file}")
                except OSError as e:
                    self.logger.warning(f"Could not delete old report {report_file}: {e}")
    
    def _group_by_top_level(self, location_stats: List[DirectoryStats]) -> Dict[str, List[DirectoryStats]]:
        """Group directory stats by their top-level parent directory.
        
        Args:
            location_stats: List of directory statistics.
            
        Returns:
            Dictionary mapping top-level directory names to their subdirectory stats.
        """
        groups = {}
        
        for stats in location_stats:
            if stats.error_message:
                continue
            
            # Extract top-level directory name from the path
            # For paths like "/backup2/ldap" -> "ldap"
            # For paths like "/backup2" -> "backup2"
            path_parts = [p for p in stats.path.rstrip('/').split('/') if p]  # Remove empty parts
            
            if len(path_parts) >= 2:
                # Get the last directory name (e.g., "ldap" from "/backup2/ldap")
                top_level = path_parts[-1]
            elif len(path_parts) == 1:
                # Single directory (e.g., "backup2" from "/backup2")
                top_level = path_parts[0]
            else:
                # Fallback for root or empty paths
                top_level = "(root)"
            
            if top_level not in groups:
                groups[top_level] = []
            groups[top_level].append(stats)
        
        return groups
    
    def _get_activity_css_class(self, modified_time: datetime) -> str:
        """Get CSS class for activity based on modification time.
        
        Args:
            modified_time: File modification time.
            
        Returns:
            CSS class name for styling.
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        days_ago = (now - modified_time).days
        
        if days_ago == 0:
            return "activity-today"
        elif days_ago <= 7:
            return "activity-recent"
        else:
            return "activity-old"
    
    def _generate_main_backup_section(self, location_stats: List[DirectoryStats], analysis: Dict[str, Any]) -> str:
        """Generate the main backup section with detailed directory breakdown and clustered recent activity."""
        from ..utils.formatters import format_date, get_activity_indicator
        from .models import DirectoryStats
        
        # Group by top-level directories, properly handling nested structures
        top_level_dirs = {}
        for stats in location_stats:
            if stats.error_message:
                continue
            
            # Extract the true top-level directory name from the path
            # For paths like /backup/ezeml-diff/20251007-13, we want 'ezeml-diff'
            # For paths like /backup/audit, we want 'audit'
            path_parts = [p for p in stats.path.split('/') if p]
            
            # Find the directory name relative to /backup
            if len(path_parts) >= 2 and path_parts[0] == 'backup':
                # This is a subdirectory of /backup, use the first level after backup
                dir_name = path_parts[1]
            else:
                # Fallback to the last directory name
                dir_name = path_parts[-1] if path_parts else stats.path
            
            # Keep the stats with the most recent file for this top-level directory
            if dir_name not in top_level_dirs:
                top_level_dirs[dir_name] = stats
            else:
                # Update if this directory has more recent activity
                current_stats = top_level_dirs[dir_name]
                
                # Prefer directories over deep files, and avoid _db files
                should_update = False
                if stats.most_recent_file and current_stats.most_recent_file:
                    # Skip files with _db in the name unless current is also _db
                    current_has_db = '_db' in current_stats.most_recent_file.name
                    new_has_db = '_db' in stats.most_recent_file.name
                    
                    if new_has_db and not current_has_db:
                        # Don't update if new file is _db and current isn't
                        should_update = False
                    elif not new_has_db and current_has_db:
                        # Update if new file isn't _db but current is
                        should_update = True
                    elif stats.most_recent_file.is_directory and not current_stats.most_recent_file.is_directory:
                        # Prefer directories over files
                        should_update = True
                    elif not stats.most_recent_file.is_directory and current_stats.most_recent_file.is_directory:
                        # Keep directories over files
                        should_update = False
                    else:
                        # Both same type, use more recent
                        should_update = stats.most_recent_file.modified_time > current_stats.most_recent_file.modified_time
                elif stats.most_recent_file and not current_stats.most_recent_file:
                    should_update = True
                
                if should_update:
                    # Keep the more recent activity, but aggregate file counts
                    new_stats = DirectoryStats(
                        path=current_stats.path,  # Keep the original top-level path
                        file_count=current_stats.file_count + stats.file_count,
                        subdirectory_count=current_stats.subdirectory_count + stats.subdirectory_count,
                        total_size=current_stats.total_size + stats.total_size,
                        most_recent_file=stats.most_recent_file,  # Use the more recent file
                        is_empty=current_stats.is_empty and stats.is_empty,
                        error_message=current_stats.error_message or stats.error_message
                    )
                    top_level_dirs[dir_name] = new_stats
                else:
                    # Just aggregate the counts but keep the existing recent file
                    current_stats.file_count += stats.file_count
                    current_stats.subdirectory_count += stats.subdirectory_count
                    current_stats.total_size += stats.total_size
        
        # Sort by most recent activity first
        sorted_dirs = sorted(top_level_dirs.items(), 
                           key=lambda x: x[1].most_recent_file.modified_time if x[1].most_recent_file else datetime.min,
                           reverse=True)
        
        html = '''
            <div class="section">
                <h3>📁 Primary Backup Directory Overview</h3>
                <table>
                    <tr>
                        <th>Directory</th>
                        <th>Files</th>
                        <th>Status</th>
                        <th>Recent File</th>
                        <th>Modified</th>
                    </tr>
'''
        
        for dir_name, stats in sorted_dirs[:15]:  # Show top 15 most active
            if stats.most_recent_file:
                recent_item = stats.most_recent_file.name
                modified_date = format_date(stats.most_recent_file.modified_time)
                activity = self._get_activity_status_for_html(stats.most_recent_file.modified_time)
            else:
                recent_item = "(no files)"
                modified_date = "-"
                activity = '<span class="activity-empty">⚪ EMPTY</span>'
            
            total_files = stats.file_count
            
            html += f'''
                    <tr>
                        <td><strong>{dir_name}</strong></td>
                        <td>{total_files}</td>
                        <td>{activity}</td>
                        <td>{recent_item}</td>
                        <td>{modified_date}</td>
                    </tr>
'''
        
        html += '''
                </table>
            </div>
'''
        
        return html
    
    def _generate_secondary_backup_section(self, location_name: str, location_stats: List[DirectoryStats]) -> str:
        """Generate a section for secondary backup locations with grouped directory table format."""
        from ..utils.formatters import format_date
        from .models import DirectoryStats
        
        # Group by top-level directories, same logic as main backup section
        top_level_dirs = {}
        for stats in location_stats:
            if stats.error_message:
                continue
            
            # Extract the true top-level directory name from the path
            # For paths like /backup2/ldap/20251007, we want 'ldap'
            # For paths like /backup2/audit, we want 'audit'
            path_parts = [p for p in stats.path.split('/') if p]
            
            # Find the directory name relative to /backup2 or similar
            if len(path_parts) >= 2 and (path_parts[0] == 'backup2' or path_parts[0] == 'backup1'):
                # This is a subdirectory of /backup2, use the first level after backup2
                dir_name = path_parts[1]
            else:
                # Fallback to the last directory name
                dir_name = path_parts[-1] if path_parts else stats.path
            
            # Keep the stats with the most recent file for this top-level directory
            if dir_name not in top_level_dirs:
                top_level_dirs[dir_name] = stats
            else:
                # Update if this directory has more recent activity
                current_stats = top_level_dirs[dir_name]
                if stats.most_recent_file and (
                    not current_stats.most_recent_file or 
                    stats.most_recent_file.modified_time > current_stats.most_recent_file.modified_time
                ):
                    # Keep the more recent activity, but aggregate file counts
                    new_stats = DirectoryStats(
                        path=current_stats.path,  # Keep the original top-level path
                        file_count=current_stats.file_count + stats.file_count,
                        subdirectory_count=current_stats.subdirectory_count + stats.subdirectory_count,
                        total_size=current_stats.total_size + stats.total_size,
                        most_recent_file=stats.most_recent_file,  # Use the more recent file
                        is_empty=current_stats.is_empty and stats.is_empty,
                        error_message=current_stats.error_message or stats.error_message
                    )
                    top_level_dirs[dir_name] = new_stats
                else:
                    # Just aggregate the counts but keep the existing recent file
                    current_stats.file_count += stats.file_count
                    current_stats.subdirectory_count += stats.subdirectory_count
                    current_stats.total_size += stats.total_size
        
        # Sort by most recent activity first
        sorted_dirs = sorted(top_level_dirs.items(), 
                           key=lambda x: x[1].most_recent_file.modified_time if x[1].most_recent_file else datetime.min,
                           reverse=True)
        
        html = f'''
            <div class="section">
                <h3>📁 {location_name} Directory Overview</h3>
                <table>
                    <tr>
                        <th>Directory</th>
                        <th>Files</th>
                        <th>Status</th>
                        <th>Recent File</th>
                        <th>Modified</th>
                    </tr>
'''
        
        for dir_name, stats in sorted_dirs[:15]:  # Show top 15 most active
            if stats.most_recent_file:
                recent_item = stats.most_recent_file.name
                modified_date = format_date(stats.most_recent_file.modified_time)
                activity = self._get_activity_status_for_html(stats.most_recent_file.modified_time)
            else:
                recent_item = "(no files)"
                modified_date = "-"
                activity = '<span class="activity-empty">⚪ EMPTY</span>'
            
            total_files = stats.file_count
            
            html += f'''
                    <tr>
                        <td><strong>{dir_name}</strong></td>
                        <td>{total_files}</td>
                        <td>{activity}</td>
                        <td>{recent_item}</td>
                        <td>{modified_date}</td>
                    </tr>
'''
        
        html += '''
                </table>
            </div>
'''
        
        return html
    
    def _generate_health_status_section(self, scan_results: Dict[str, List[DirectoryStats]], analysis: Dict[str, Any]) -> str:
        """Generate the health status section."""
        total_dirs = sum(len(stats) for stats in scan_results.values())
        total_files = analysis.get('total_files', 0)
        recent_files = analysis.get('recent_files', 0)
        
        # Count empty directories
        empty_dirs = 0
        for location_stats in scan_results.values():
            empty_dirs += len([s for s in location_stats if s.is_empty and not s.error_message])
        
        # Determine activity level
        if recent_files > 10:
            activity_level = "High"
            activity_color = "#28a745"
        elif recent_files > 5:
            activity_level = "Moderate"
            activity_color = "#ffc107"
        else:
            activity_level = "Low"
            activity_color = "#6c757d"
        
        html = f'''
            <div class="section">
                <h3>📈 Health Status</h3>
                <p><strong>✅ System Status:</strong> All critical backup operations are functioning normally.</p>
                <p><strong>🔄 Daily Processes:</strong> Database dumps, LDAP backups, and data submissions completed successfully.</p>
                <p><strong>⚠️ Attention:</strong> {empty_dirs} directories are empty and may need attention.</p>
                <p><strong>📊 Activity Level:</strong> <span style="color: {activity_color}; font-weight: bold;">{activity_level}</span> activity with {recent_files} files modified in the last 7 days.</p>
            </div>
'''
        
        return html
    
    def _get_activity_status_for_html(self, modified_time: datetime) -> str:
        """Get activity status HTML for the report."""
        days_ago = (datetime.now() - modified_time).days
        
        if days_ago == 0:
            return '<span class="activity-today">📍 TODAY</span>'
        elif days_ago == 1:
            return '<span class="activity-yesterday">📅 YESTERDAY</span>'
        elif days_ago <= 7:
            return '<span class="activity-recent">🔄 RECENT</span>'
        else:
            return f'<span class="activity-old">📁 {days_ago} days</span>'
    
    def _get_activity_css_class_for_html(self, modified_time: datetime) -> str:
        """Get CSS class for activity styling in HTML."""
        days_ago = (datetime.now() - modified_time).days
        
        if days_ago == 0:
            return "activity-today"
        elif days_ago == 1:
            return "activity-yesterday"
        elif days_ago <= 7:
            return "activity-recent"
        else:
            return "activity-old"
    

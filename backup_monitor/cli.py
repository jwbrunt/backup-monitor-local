"""Command-line interface for backup monitor."""

import logging
import sys
from pathlib import Path
import click
from typing import Optional

from .core.monitor import BackupMonitor
from .config.config_manager import ConfigManager


def setup_logging(level: str, log_file: Optional[str] = None):
    """Set up logging configuration."""
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            click.echo(f"Warning: Could not set up file logging: {e}", err=True)


@click.group()
@click.option('--config', '-c', 'config_path',
              help='Path to configuration file')
@click.option('--log-level', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
              help='Logging level')
@click.option('--log-file',
              help='Log file path')
@click.pass_context
def cli(ctx, config_path: Optional[str], log_level: str, log_file: Optional[str]):
    """Backup Monitor - Monitor backup directories across multiple locations."""
    
    # Ensure context exists
    ctx.ensure_object(dict)
    
    # Set up logging first
    setup_logging(log_level, log_file)
    
    # Store configuration path
    ctx.obj['config_path'] = config_path


@cli.command()
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text',
              help='Output format')
@click.pass_context
def scan(ctx, output: str):
    """Scan all configured backup locations."""
    try:
        # Initialize monitor
        monitor = BackupMonitor(ctx.obj.get('config_path'))
        
        click.echo("Starting backup location scan...")
        
        # Run scan
        scan_results = monitor.scan_all_locations()
        
        if output == 'json':
            import json
            from datetime import datetime
            
            # Convert results to JSON-serializable format
            json_results = {}
            for location, stats_list in scan_results.items():
                json_results[location] = []
                for stats in stats_list:
                    stat_dict = {
                        'path': stats.path,
                        'file_count': stats.file_count,
                        'subdirectory_count': stats.subdirectory_count,
                        'total_size': stats.total_size,
                        'is_empty': stats.is_empty,
                        'error_message': stats.error_message
                    }
                    
                    if stats.most_recent_file:
                        stat_dict['most_recent_file'] = {
                            'name': stats.most_recent_file.name,
                            'path': stats.most_recent_file.path,
                            'size': stats.most_recent_file.size,
                            'modified_time': stats.most_recent_file.modified_time.isoformat()
                        }
                    else:
                        stat_dict['most_recent_file'] = None
                    
                    json_results[location].append(stat_dict)
            
            click.echo(json.dumps(json_results, indent=2))
        
        else:
            # Text output
            click.echo("\nScan Results:")
            click.echo("=" * 50)
            
            total_locations = len(scan_results)
            total_directories = sum(len(stats) for stats in scan_results.values())
            
            click.echo(f"Scanned {total_locations} backup locations")
            click.echo(f"Found {total_directories} directories total")
            click.echo("")
            
            for location_name, location_stats in scan_results.items():
                click.echo(f"📂 {location_name}:")
                
                if not location_stats:
                    click.echo("  No directories found")
                    continue
                
                # Count stats
                successful = len([s for s in location_stats if not s.error_message])
                errors = len([s for s in location_stats if s.error_message])
                empty = len([s for s in location_stats if s.is_empty and not s.error_message])
                
                click.echo(f"  Directories: {len(location_stats)} ({successful} accessible, {errors} errors)")
                click.echo(f"  Empty directories: {empty}")
                
                # Show recent activity
                recent_files = []
                for stats in location_stats:
                    if stats.most_recent_file and not stats.error_message:
                        recent_files.append((stats.most_recent_file.modified_time, stats.most_recent_file.name))
                
                if recent_files:
                    recent_files.sort(reverse=True)  # Most recent first
                    most_recent = recent_files[0]
                    click.echo(f"  Most recent file: {most_recent[1]} ({most_recent[0].strftime('%Y-%m-%d %H:%M')})")
                
                click.echo("")
    
    except Exception as e:
        click.echo(f"Error during scan: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--format', '-f', type=click.Choice(['text', 'html', 'both']), default='both',
              help='Report format')
@click.option('--email/--no-email', default=True,
              help='Send report via email')
@click.option('--save/--no-save', default=True,
              help='Save report to local files')
@click.pass_context
def report(ctx, format: str, email: bool, save: bool):
    """Generate and optionally send backup reports."""
    try:
        # Initialize monitor
        monitor = BackupMonitor(ctx.obj.get('config_path'))
        
        click.echo("Running full backup scan and report generation...")
        
        # Run full scan with options
        results = monitor.run_full_scan(send_email=email, save_reports=save)
        
        click.echo("✅ Backup scan completed successfully")
        
        # Show summary
        scan_results = results['scan_results']
        total_locations = len(scan_results)
        total_directories = sum(len(stats) for stats in scan_results.values())
        
        click.echo(f"\n📊 Summary:")
        click.echo(f"  Locations scanned: {total_locations}")
        click.echo(f"  Directories found: {total_directories}")
        
        # Show report info
        reports = results['reports']
        if 'text' in reports:
            click.echo("  📄 Text report generated")
        if 'html' in reports:
            click.echo("  🌐 HTML report generated")
        
        if save:
            click.echo("  💾 Reports saved locally")
        
        if email and monitor.email_reporter:
            click.echo("  📧 Email report sent")
        elif email:
            click.echo("  ⚠️  Email not configured - report not sent")
        
        click.echo(f"\n🕒 Completed at: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def overview(ctx):
    """Show a quick overview of all backup locations."""
    try:
        # Initialize monitor
        monitor = BackupMonitor(ctx.obj.get('config_path'))
        
        click.echo("Getting backup overview...")
        
        # Run scan
        scan_results = monitor.scan_all_locations()
        
        click.echo("\n🗂️  Backup Directory Overview")
        click.echo("=" * 50)
        
        for location_name, location_stats in scan_results.items():
            click.echo(f"\n📍 {location_name}")
            click.echo("-" * len(location_name))
            
            if not location_stats:
                click.echo("   ❌ No data available")
                continue
            
            # Get location summary
            summary = monitor.analyzer.get_location_summary(location_stats)
            
            click.echo(f"   📁 Directories: {summary['directories']}")
            click.echo(f"   📄 Files: {summary['files']:,}")
            click.echo(f"   💾 Total size: {_format_size(summary['total_size'])}")
            
            if summary['error_directories'] > 0:
                click.echo(f"   ⚠️  Errors: {summary['error_directories']} directories inaccessible")
            
            if summary['empty_directories'] > 0:
                click.echo(f"   📭 Empty: {summary['empty_directories']} directories")
            
            if summary['recent_files'] > 0:
                click.echo(f"   🆕 Recent activity: {summary['recent_files']} files")
            else:
                click.echo("   😴 No recent activity")
            
            if summary['most_recent_activity']:
                recent = summary['most_recent_activity']
                click.echo(f"   🕒 Last activity: {recent['file']} ({recent['modified'].strftime('%Y-%m-%d %H:%M')})")
    
    except Exception as e:
        click.echo(f"Error getting overview: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def test_email(ctx):
    """Send a test email to verify email configuration."""
    try:
        # Initialize monitor
        monitor = BackupMonitor(ctx.obj.get('config_path'))
        
        if not monitor.email_reporter:
            click.echo("❌ Email not configured - cannot send test email", err=True)
            sys.exit(1)
        
        click.echo("Sending test email...")
        
        # Validate configuration first
        errors = monitor.email_reporter.validate_configuration()
        if errors:
            click.echo("❌ Email configuration errors:")
            for error in errors:
                click.echo(f"   • {error}")
            sys.exit(1)
        
        # Send test email
        success = monitor.email_reporter.send_test_email()
        
        if success:
            click.echo("✅ Test email sent successfully!")
            click.echo(f"   Recipients: {', '.join(monitor.email_reporter.to_addresses)}")
        else:
            click.echo("❌ Failed to send test email", err=True)
            sys.exit(1)
    
    except Exception as e:
        click.echo(f"Error sending test email: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def validate_config(ctx):
    """Validate configuration file."""
    try:
        config_manager = ConfigManager(ctx.obj.get('config_path'))
        config = config_manager.load_config()
        
        click.echo("✅ Configuration loaded successfully")
        
        # Show basic config info
        locations = config_manager.get_backup_locations()
        email_config = config_manager.get_email_config()
        
        click.echo(f"\n📊 Configuration Summary:")
        click.echo(f"   Backup locations: {len(locations)}")
        
        for i, location in enumerate(locations, 1):
            click.echo(f"     {i}. {location['name']} ({location.get('type', 'local')}): {location['path']}")
        
        if email_config:
            click.echo(f"   📧 Email configured: {email_config.get('from_address', 'N/A')}")
            click.echo(f"   📬 Recipients: {len(email_config.get('to_addresses', []))}")
        else:
            click.echo("   📧 Email: Not configured")
        
        # Validate email if configured
        if email_config:
            from .reporters.email_reporter import EmailReporter
            email_reporter = EmailReporter(
                smtp_server=email_config.get('smtp_server'),
                smtp_port=email_config.get('smtp_port', 587),
                smtp_user=email_config.get('smtp_user'),
                smtp_pass=email_config.get('smtp_pass'),
                from_address=email_config.get('from_address'),
                to_addresses=email_config.get('to_addresses', [])
            )
            
            email_errors = email_reporter.validate_configuration()
            if email_errors:
                click.echo("\n⚠️  Email configuration issues:")
                for error in email_errors:
                    click.echo(f"     • {error}")
            else:
                click.echo("\n✅ Email configuration valid")
    
    except Exception as e:
        click.echo(f"❌ Configuration validation failed: {e}", err=True)
        sys.exit(1)


def _format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}PB"


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()
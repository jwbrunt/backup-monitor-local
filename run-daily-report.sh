#!/bin/bash
# Daily backup monitoring report

set -e

cd /home/pasta/backup-monitor-local

# Run the backup monitor
/home/pasta/miniconda3/bin/python3 << 'PYRUN'
import sys
sys.path.insert(0, '/home/pasta/backup-monitor-local')

from backup_monitor.core.monitor import BackupMonitor

try:
    monitor = BackupMonitor('/home/pasta/.backup-monitor/config.yaml')
    scan_results = monitor.scan_all_locations()
    reports = monitor.generate_report(scan_results)
    success = monitor.send_email_report(reports)
    
    if success:
        print("✅ Backup monitor report sent successfully")
        sys.exit(0)
    else:
        print("❌ Failed to send email report")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYRUN

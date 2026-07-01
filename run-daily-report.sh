#!/bin/bash
# Daily backup monitoring report
# 
# Edit the paths below to match your installation:
#   INSTALL_DIR: where backup-monitor-local is installed
#   CONFIG_FILE: path to your config.yaml
#   PYTHON: path to your Python interpreter

set -e

# Configuration - edit these paths for your environment
INSTALL_DIR="$HOME/backup-monitor-local"
CONFIG_FILE="$HOME/.backup-monitor/config.yaml"
PYTHON="python3"

cd "$INSTALL_DIR"

# Run the backup monitor
$PYTHON << PYRUN
import sys
sys.path.insert(0, '$INSTALL_DIR')

from backup_monitor.core.monitor import BackupMonitor

try:
    monitor = BackupMonitor('$CONFIG_FILE')
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

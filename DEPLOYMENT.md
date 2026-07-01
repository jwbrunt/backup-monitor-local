# Deployment Guide - Backup Monitor v2.0

## Installation

```bash
# Clone the repository
git clone https://github.com/jwbrunt/backup-monitor-local.git
cd backup-monitor-local

# Install with pip
pip install -e .

# Or install dependencies only
pip install pyyaml jinja2 click python-dateutil tabulate colorama
```

## Configuration

1. Create config directory:
```bash
mkdir -p ~/.backup-monitor/logs
```

2. Copy and edit the example config:
```bash
cp config.example.yaml ~/.backup-monitor/config.yaml
# Edit with your paths and email settings
```

## Usage

### Manual Run
```bash
backup-monitor -c ~/.backup-monitor/config.yaml report --format html --email
```

### Cron Job (Daily at 7 AM)
```bash
crontab -e
# Add:
0 7 * * * /path/to/backup-monitor-local/run-daily-report.sh >> ~/.backup-monitor/logs/backup_monitor.log 2>&1
```

## Features

- ✅ Multi-directory backup monitoring
- ✅ HTML and text report generation
- ✅ Email delivery (SMTP or sendEmail)
- ✅ Configurable staleness thresholds
- ✅ Subdirectory recency detection

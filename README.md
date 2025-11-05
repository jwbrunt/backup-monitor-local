# Backup Monitor

A standalone backup monitoring system for local directories with automated email reports. Built in Python for easy deployment and maintenance.

## Features

- **Multi-Directory Support**: Monitor multiple local backup locations
- **Flexible Configuration**: YAML-based configuration
- **Email Reports**: Automated HTML and text email reports via SMTP
- **Activity Tracking**: Track recent file activity with visual indicators
- **Performance Optimized**: Configurable limits and exclusions for large directories
- **Standalone Deployment**: Self-contained installation with virtual environment
- **CLI Interface**: Rich command-line interface with multiple operations
- **Logging**: Comprehensive logging with configurable levels
- **Scheduling Support**: Systemd timer and cron integration

## Quick Start

### Prerequisites

- Python 3.8 or later
- pip (Python package manager)

### Installation

1. **Clone or download the repository**:
   ```bash
   git clone <repository-url>
   cd backup-monitor
   ```

2. **Run the installation script**:
   ```bash
   ./install.sh
   ```

3. **Configure the system**:
   ```bash
   # Edit the configuration file
   nano ~/.backup-monitor/config.yaml
   ```

4. **Test the installation**:
   ```bash
   ./backup-monitor validate-config
   ./backup-monitor scan
   ```

### Manual Installation

If you prefer manual installation:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Copy configuration
mkdir -p ~/.backup-monitor
cp config.example.yaml ~/.backup-monitor/config.yaml
```

## Configuration

### Basic Configuration

Create or edit `~/.backup-monitor/config.yaml`:

```yaml
# Local backup directories to monitor
backup_locations:
  - name: "Primary Backup"
    type: "local"
    path: "/backup"
    description: "Main backup directory"
    exclude_patterns:
      - "/backup/tmp"
      - "/backup/cache"
    max_depth: 3

# Email configuration
email:
  smtp_server: "smtp.example.com"
  smtp_port: 587
  smtp_user: "your-username"
  smtp_pass: "your-password"
  from_address: "backup-monitor@example.com"
  to_addresses:
    - "admin@example.com"

# Monitoring settings
monitoring:
  max_depth: 3
  days_back: 7
  max_dirs: 200
```

## Usage

### Command Line Interface

```bash
# Validate configuration
./backup-monitor validate-config

# Scan directories (no email)
./backup-monitor scan

# Generate and send email report
./backup-monitor report

# Test email configuration
./backup-monitor test-email
```

### Scheduling

#### Using Systemd

```bash
# Copy service and timer files
sudo cp backup-monitor.service /etc/systemd/system/
sudo cp backup-monitor.timer /etc/systemd/system/

# Enable and start the timer
sudo systemctl enable backup-monitor.timer
sudo systemctl start backup-monitor.timer

# Check status
sudo systemctl status backup-monitor.timer
```

#### Using Cron

```bash
# Edit crontab
crontab -e

# Add daily report at 7:00 AM
0 7 * * * /path/to/backup-monitor report
```

## Development

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
python -m pytest tests/
```

### Project Structure

```
backup-monitor/
├── backup_monitor/
│   ├── config/         # Configuration management
│   ├── core/           # Core monitoring logic
│   ├── reporters/      # Email reporting
│   ├── utils/          # Utility functions
│   └── cli.py          # Command-line interface
├── tests/              # Test suite
├── config.example.yaml # Example configuration
├── install.sh          # Installation script
├── requirements.txt    # Python dependencies
└── setup.py            # Package setup
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

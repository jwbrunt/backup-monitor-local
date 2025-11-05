#!/bin/bash

# Backup Monitor Installation Script
# This script sets up the backup monitor system on a new machine

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INSTALL_DIR="${INSTALL_DIR:-$HOME/backup-monitor}"
PYTHON_CMD="${PYTHON_CMD:-python3}"
VENV_DIR="${VENV_DIR:-$INSTALL_DIR/venv}"
CONFIG_DIR="${CONFIG_DIR:-$HOME/.backup-monitor}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

check_requirements() {
    log_step "Checking system requirements..."
    
    # Check if Python 3.8+ is available
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.8 or later."
        exit 1
    fi
    
    # Check Python version
    python_version=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    python_major=$(echo "$python_version" | cut -d'.' -f1)
    python_minor=$(echo "$python_version" | cut -d'.' -f2)
    
    if [[ "$python_major" -lt 3 ]] || [[ "$python_major" -eq 3 && "$python_minor" -lt 8 ]]; then
        log_error "Python 3.8+ required, found $python_version"
        exit 1
    fi
    
    log_info "Python $python_version found ✓"
    
    # Check if pip is available
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        log_error "pip not found. Please install pip."
        exit 1
    fi
    
    log_info "pip found ✓"
    
    # Check if git is available (for cloning)
    if ! command -v git &> /dev/null; then
        log_warn "git not found - manual installation will be required"
    else
        log_info "git found ✓"
    fi
}

create_virtual_environment() {
    log_step "Creating Python virtual environment..."
    
    if [[ -d "$VENV_DIR" ]]; then
        log_warn "Virtual environment already exists at $VENV_DIR"
        read -p "Remove existing environment? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
        else
            log_info "Using existing virtual environment"
            return 0
        fi
    fi
    
    $PYTHON_CMD -m venv "$VENV_DIR"
    log_info "Virtual environment created at $VENV_DIR"
}

install_dependencies() {
    log_step "Installing Python dependencies..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install backup monitor
    if [[ -f "$INSTALL_DIR/setup.py" ]]; then
        log_info "Installing from local source..."
        cd "$INSTALL_DIR"
        pip install -e .
    else
        log_error "setup.py not found at $INSTALL_DIR"
        exit 1
    fi
    
    log_info "Dependencies installed ✓"
}

create_config_directory() {
    log_step "Setting up configuration directory..."
    
    mkdir -p "$CONFIG_DIR"
    
    # Copy example config if it doesn't exist
    if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
        if [[ -f "$INSTALL_DIR/config.example.yaml" ]]; then
            cp "$INSTALL_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
            log_info "Example configuration copied to $CONFIG_DIR/config.yaml"
            log_warn "Please edit $CONFIG_DIR/config.yaml with your settings"
        else
            log_warn "Example configuration not found"
        fi
    else
        log_info "Configuration file already exists at $CONFIG_DIR/config.yaml"
    fi
    
    # Create other directories
    mkdir -p "$CONFIG_DIR/reports"
    mkdir -p "$CONFIG_DIR/logs"
    
    log_info "Configuration directory set up ✓"
}

create_wrapper_script() {
    log_step "Creating wrapper script..."
    
    local wrapper_script="$INSTALL_DIR/backup-monitor"
    
    cat > "$wrapper_script" << EOF
#!/bin/bash
# Backup Monitor wrapper script
# Activates the virtual environment and runs the backup monitor

set -e

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="\$SCRIPT_DIR/venv"

if [[ ! -f "\$VENV_DIR/bin/activate" ]]; then
    echo "Error: Virtual environment not found at \$VENV_DIR"
    echo "Please run the installation script first."
    exit 1
fi

# Activate virtual environment
source "\$VENV_DIR/bin/activate"

# Run backup monitor with all arguments
exec backup-monitor "\$@"
EOF
    
    chmod +x "$wrapper_script"
    log_info "Wrapper script created at $wrapper_script"
}

create_systemd_service() {
    log_step "Creating systemd service file (optional)..."
    
    local service_file="$INSTALL_DIR/backup-monitor.service"
    
    cat > "$service_file" << EOF
[Unit]
Description=Backup Monitor Daily Report
After=network.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$INSTALL_DIR/backup-monitor report
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    log_info "Systemd service file created at $service_file"
    log_info "To install: sudo cp $service_file /etc/systemd/system/"
    log_info "To enable daily reports: sudo systemctl enable backup-monitor.timer"
    
    # Create timer file
    local timer_file="$INSTALL_DIR/backup-monitor.timer"
    
    cat > "$timer_file" << EOF
[Unit]
Description=Run Backup Monitor Daily
Requires=backup-monitor.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF
    
    log_info "Systemd timer file created at $timer_file"
}

show_next_steps() {
    log_step "Installation complete!"
    
    echo
    echo "Next steps:"
    echo "==========="
    echo "1. Edit configuration file: $CONFIG_DIR/config.yaml"
    echo "2. Test configuration: $INSTALL_DIR/backup-monitor validate-config"
    echo "3. Run a test scan: $INSTALL_DIR/backup-monitor scan"
    echo "4. Test email (if configured): $INSTALL_DIR/backup-monitor test-email"
    echo "5. Generate a report: $INSTALL_DIR/backup-monitor report"
    echo
    echo "For daily automated reports:"
    echo "  • Copy systemd files: sudo cp $INSTALL_DIR/backup-monitor.* /etc/systemd/system/"
    echo "  • Enable timer: sudo systemctl enable --now backup-monitor.timer"
    echo
    echo "Or add to cron:"
    echo "  0 7 * * * $INSTALL_DIR/backup-monitor report > /dev/null 2>&1"
    echo
    echo "Documentation: $INSTALL_DIR/README.md"
    echo
}

# Main installation process
main() {
    echo "Backup Monitor Installation"
    echo "=========================="
    echo
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --python)
                PYTHON_CMD="$2"
                shift 2
                ;;
            --config-dir)
                CONFIG_DIR="$2"
                shift 2
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo
                echo "Options:"
                echo "  --install-dir DIR    Installation directory (default: $INSTALL_DIR)"
                echo "  --python CMD         Python command (default: $PYTHON_CMD)"
                echo "  --config-dir DIR     Configuration directory (default: $CONFIG_DIR)"
                echo "  --help               Show this help"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Update derived paths
    VENV_DIR="$INSTALL_DIR/venv"
    
    log_info "Installing to: $INSTALL_DIR"
    log_info "Configuration: $CONFIG_DIR"
    log_info "Python: $PYTHON_CMD"
    echo
    
    check_requirements
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    create_virtual_environment
    install_dependencies
    create_config_directory
    create_wrapper_script
    create_systemd_service
    show_next_steps
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
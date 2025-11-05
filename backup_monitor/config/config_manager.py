"""Configuration management for the backup monitor system."""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from .config_validator import ConfigValidator


class ConfigManager:
    """Manages configuration loading and validation for backup monitoring."""
    
    DEFAULT_CONFIG_LOCATIONS = [
        "config.yaml",
        "config.yml", 
        os.path.expanduser("~/.backup-monitor/config.yaml"),
        os.path.expanduser("~/.backup-monitor/config.yml"),
        "/etc/backup-monitor/config.yaml",
        "/etc/backup-monitor/config.yml"
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Optional path to config file. If not provided,
                        will search in default locations.
        """
        self.config_path = config_path
        self.config_data: Dict[str, Any] = {}
        self.validator = ConfigValidator()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            Dictionary containing configuration data.
            
        Raises:
            FileNotFoundError: If config file cannot be found.
            ValueError: If config file is invalid.
        """
        config_file = self._find_config_file()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading config file {config_file}: {e}")
        
        # Validate configuration
        self.validator.validate(self.config_data)
        
        # Set defaults
        self._set_defaults()
        
        return self.config_data
    
    def _find_config_file(self) -> str:
        """Find configuration file in default locations.
        
        Returns:
            Path to configuration file.
            
        Raises:
            FileNotFoundError: If no config file is found.
        """
        if self.config_path:
            if os.path.exists(self.config_path):
                return self.config_path
            else:
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        for location in self.DEFAULT_CONFIG_LOCATIONS:
            if os.path.exists(location):
                return location
        
        raise FileNotFoundError(
            f"Configuration file not found in any of these locations:\n" +
            "\n".join(f"  - {loc}" for loc in self.DEFAULT_CONFIG_LOCATIONS) +
            "\n\nPlease copy config.example.yaml to config.yaml and customize it."
        )
    
    def _set_defaults(self):
        """Set default values for optional configuration parameters."""
        defaults = {
            'monitoring': {
                'max_depth': 3,
                'days_back': 7,
                'max_dirs': 200,
                'file_size_limit_mb': 100,
                'timeout_seconds': 300
            },
            'logging': {
                'level': 'INFO',
                'file': 'backup_monitor.log',
                'max_size_mb': 10,
                'backup_count': 5
            },
            'reports': {
                'format': 'both',  # html, text, both
                'save_local': True,
                'retention_days': 30
            }
        }
        
        # Merge defaults with existing config
        for section, section_defaults in defaults.items():
            if section not in self.config_data:
                self.config_data[section] = {}
            for key, value in section_defaults.items():
                if key not in self.config_data[section]:
                    self.config_data[section][key] = value
    
    def get_backup_locations(self) -> List[Dict[str, Any]]:
        """Get all configured backup locations.
        
        Returns:
            List of backup location configurations.
        """
        return self.config_data.get('backup_locations', [])
    
    def get_email_config(self) -> Dict[str, Any]:
        """Get email configuration.
        
        Returns:
            Email configuration dictionary.
        """
        return self.config_data.get('email', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration.
        
        Returns:
            Monitoring configuration dictionary.
        """
        return self.config_data.get('monitoring', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration.
        
        Returns:
            Logging configuration dictionary.
        """
        return self.config_data.get('logging', {})
    
    def get_reports_config(self) -> Dict[str, Any]:
        """Get reports configuration.
        
        Returns:
            Reports configuration dictionary.
        """
        return self.config_data.get('reports', {})
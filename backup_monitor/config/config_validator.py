"""Configuration validation for backup monitor."""

from typing import Dict, List, Any


class ConfigValidator:
    """Validates backup monitor configuration."""
    
    REQUIRED_SECTIONS = ['backup_locations']
    REQUIRED_EMAIL_FIELDS = ['smtp_server', 'smtp_user', 'smtp_pass', 'from_address', 'to_addresses']
    
    def validate(self, config: Dict[str, Any]) -> None:
        """Validate configuration data.
        
        Args:
            config: Configuration dictionary to validate.
            
        Raises:
            ValueError: If configuration is invalid.
        """
        self._validate_structure(config)
        self._validate_backup_locations(config.get('backup_locations', []))
        
        # Validate email config if present
        if 'email' in config:
            self._validate_email_config(config['email'])
    
    def _validate_structure(self, config: Dict[str, Any]) -> None:
        """Validate basic configuration structure.
        
        Args:
            config: Configuration dictionary.
            
        Raises:
            ValueError: If required sections are missing.
        """
        missing_sections = []
        for section in self.REQUIRED_SECTIONS:
            if section not in config:
                missing_sections.append(section)
        
        if missing_sections:
            raise ValueError(f"Missing required configuration sections: {missing_sections}")
    
    def _validate_backup_locations(self, locations: List[Dict[str, Any]]) -> None:
        """Validate backup locations configuration.
        
        Args:
            locations: List of backup location configurations.
            
        Raises:
            ValueError: If backup locations are invalid.
        """
        if not locations:
            raise ValueError("At least one backup location must be configured")
        
        for i, location in enumerate(locations):
            if not isinstance(location, dict):
                raise ValueError(f"Backup location {i} must be a dictionary")
            
            # Check required fields
            required_fields = ['name', 'path']
            missing_fields = [field for field in required_fields if field not in location]
            if missing_fields:
                raise ValueError(f"Backup location {i} missing required fields: {missing_fields}")
            
            # Validate path
            if not location['path']:
                raise ValueError(f"Backup location {i} path cannot be empty")
            
            # Validate connection type
            connection_type = location.get('type', 'local')
            if connection_type not in ['local']:
                raise ValueError(f"Backup location {i} has invalid type: {connection_type}")
            
            # Validate SSH connection if needed
    
    
    def _validate_email_config(self, email_config: Dict[str, Any]) -> None:
        """Validate email configuration.
        
        Args:
            email_config: Email configuration dictionary.
            
        Raises:
            ValueError: If email configuration is invalid.
        """
        missing_fields = [field for field in self.REQUIRED_EMAIL_FIELDS if field not in email_config]
        if missing_fields:
            raise ValueError(f"Email configuration missing required fields: {missing_fields}")
        
        # Validate port if provided
        if 'smtp_port' in email_config:
            try:
                port = int(email_config['smtp_port'])
                if not (1 <= port <= 65535):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError(f"Email configuration has invalid SMTP port: {email_config['smtp_port']}")
        
        # Validate to_addresses is a list
        to_addresses = email_config.get('to_addresses', [])
        if not isinstance(to_addresses, list) or not to_addresses:
            raise ValueError("Email to_addresses must be a non-empty list")
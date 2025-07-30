#!/usr/bin/env python3
"""
Squid Service Monitor - Production-ready service monitoring script
Monitors Squid proxy service status and sends email alerts
"""

import os
import sys
import time
import json
import yaml
import socket
import logging
import logging.handlers
import argparse
import subprocess
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

__version__ = "1.0.0"

class Config:
    """Configuration management for the monitor"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self._validate_config()
    
    def _load_config(self, config_file: Optional[str]) -> Dict:
        """Load configuration from file and environment variables"""
        config = {
            'smtp': {
                'server': os.getenv('SMTP_SERVER', 'smtp.example.com'),
                'port': int(os.getenv('SMTP_PORT', '25')),
                'use_tls': os.getenv('SMTP_USE_TLS', 'false').lower() == 'true',
                'username': os.getenv('SMTP_USERNAME', ''),
                'password': os.getenv('SMTP_PASSWORD', ''),
                'from_address': os.getenv('SMTP_FROM', 'squid-noreply@example.com'),
                'to_addresses': os.getenv('SMTP_TO', 'admin@example.com').split(','),
                'timeout': int(os.getenv('SMTP_TIMEOUT', '30'))
            },
            'monitoring': {
                'service_name': os.getenv('SERVICE_NAME', 'squid'),
                'check_interval': int(os.getenv('CHECK_INTERVAL', '300')),
                'state_file': os.getenv('STATE_FILE', '/var/lib/squid-monitor/state.json'),
                'log_file': os.getenv('LOG_FILE', '/var/log/squid-monitor/monitor.log'),
                'log_level': os.getenv('LOG_LEVEL', 'INFO'),
                'alert_cooldown': int(os.getenv('ALERT_COOLDOWN', '3600')),
                'retry_attempts': int(os.getenv('RETRY_ATTEMPTS', '3')),
                'retry_delay': int(os.getenv('RETRY_DELAY', '5'))
            },
            'features': {
                'dry_run': os.getenv('DRY_RUN', 'false').lower() == 'true',
                'enable_syslog': os.getenv('ENABLE_SYSLOG', 'true').lower() == 'true',
                'enable_webhooks': os.getenv('ENABLE_WEBHOOKS', 'false').lower() == 'true',
                'webhook_url': os.getenv('WEBHOOK_URL', '')
            }
        }
        
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    self._merge_config(config, file_config)
        
        return config
    
    def _merge_config(self, base: Dict, override: Dict) -> None:
        """Recursively merge configuration dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        if not email_pattern.match(self.config['smtp']['from_address']):
            raise ValueError(f"Invalid from_address: {self.config['smtp']['from_address']}")
        
        for email in self.config['smtp']['to_addresses']:
            if not email_pattern.match(email.strip()):
                raise ValueError(f"Invalid to_address: {email}")
        
        if self.config['smtp']['port'] not in range(1, 65536):
            raise ValueError(f"Invalid SMTP port: {self.config['smtp']['port']}")

class Logger:
    """Structured logging with multiple outputs"""
    
    def __init__(self, config: Dict):
        self.logger = logging.getLogger('squid-monitor')
        self.logger.setLevel(getattr(logging, config['monitoring']['log_level']))
        self.logger.handlers = []
        
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"correlation_id": "%(correlation_id)s", "hostname": "%(hostname)s", '
            '"message": "%(message)s"}'
        )
        
        # File handler
        log_dir = Path(config['monitoring']['log_file']).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            config['monitoring']['log_file'],
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Syslog handler
        if config['features']['enable_syslog']:
            syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
            syslog_handler.setFormatter(formatter)
            self.logger.addHandler(syslog_handler)
        
        # Console handler for debug mode
        if config['monitoring']['log_level'] == 'DEBUG':
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def log(self, level: str, message: str, correlation_id: str) -> None:
        """Log message with context"""
        extra = {
            'correlation_id': correlation_id,
            'hostname': socket.gethostname()
        }
        getattr(self.logger, level.lower())(message, extra=extra)

class StateManager:
    """Manage monitoring state to prevent alert fatigue"""
    
    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {
            'last_check': None,
            'last_status': None,
            'last_alert_time': None,
            'consecutive_failures': 0,
            'last_success_time': None
        }
    
    def save_state(self) -> None:
        """Save current state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def should_send_alert(self, current_status: bool, cooldown_seconds: int) -> bool:
        """Determine if an alert should be sent based on state"""
        if current_status:  # Service is up
            if self.state['last_status'] is False:
                # Recovery alert
                return True
            return False
        
        # Service is down
        if self.state['last_status'] is None or self.state['last_status'] is True:
            # First failure or transition from up to down
            return True
        
        # Check cooldown period
        if self.state['last_alert_time']:
            last_alert = datetime.fromisoformat(self.state['last_alert_time'])
            if datetime.now() - last_alert > timedelta(seconds=cooldown_seconds):
                return True
        
        return False
    
    def update_state(self, status: bool, alert_sent: bool = False) -> None:
        """Update state after check"""
        self.state['last_check'] = datetime.now().isoformat()
        self.state['last_status'] = status
        
        if status:
            self.state['consecutive_failures'] = 0
            self.state['last_success_time'] = datetime.now().isoformat()
        else:
            self.state['consecutive_failures'] += 1
        
        if alert_sent:
            self.state['last_alert_time'] = datetime.now().isoformat()
        
        self.save_state()

class ServiceMonitor:
    """Core service monitoring functionality"""
    
    def __init__(self, config: Config, logger: Logger, state_manager: StateManager):
        self.config = config.config
        self.logger = logger
        self.state_manager = state_manager
        self.correlation_id = str(uuid.uuid4())
    
    def check_service_status(self, service_name: str) -> Tuple[bool, str]:
        """Check if service is running using systemctl"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            is_active = result.returncode == 0
            status = result.stdout.strip()
            
            self.logger.log('DEBUG', f"Service {service_name} status: {status}", self.correlation_id)
            
            return is_active, status
        except subprocess.TimeoutExpired:
            self.logger.log('ERROR', f"Timeout checking service {service_name}", self.correlation_id)
            return False, "timeout"
        except Exception as e:
            self.logger.log('ERROR', f"Error checking service {service_name}: {str(e)}", self.correlation_id)
            return False, f"error: {str(e)}"
    
    def get_system_stats(self) -> Dict:
        """Gather system resource statistics"""
        stats = {}
        
        try:
            # CPU usage
            with open('/proc/stat', 'r') as f:
                cpu_line = f.readline()
                cpu_times = list(map(int, cpu_line.split()[1:5]))
                idle_time = cpu_times[3]
                total_time = sum(cpu_times)
                stats['cpu_usage'] = round((1 - idle_time/total_time) * 100, 2)
        except Exception as e:
            self.logger.log('WARNING', f"Failed to get CPU stats: {str(e)}", self.correlation_id)
            stats['cpu_usage'] = 'N/A'
        
        try:
            # Memory usage
            with open('/proc/meminfo', 'r') as f:
                meminfo = dict((line.split()[0].rstrip(':'), int(line.split()[1])) 
                              for line in f.readlines())
                total = meminfo['MemTotal']
                available = meminfo.get('MemAvailable', meminfo['MemFree'])
                stats['memory_usage'] = round((1 - available/total) * 100, 2)
        except Exception as e:
            self.logger.log('WARNING', f"Failed to get memory stats: {str(e)}", self.correlation_id)
            stats['memory_usage'] = 'N/A'
        
        try:
            # Disk usage
            result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    stats['disk_usage'] = parts[4] if len(parts) > 4 else 'N/A'
            else:
                stats['disk_usage'] = 'N/A'
        except Exception as e:
            self.logger.log('WARNING', f"Failed to get disk stats: {str(e)}", self.correlation_id)
            stats['disk_usage'] = 'N/A'
        
        return stats
    
    def get_recent_logs(self, service_name: str, lines: int = 50) -> str:
        """Get recent logs from the service"""
        try:
            result = subprocess.run(
                ['journalctl', '-u', service_name, '-n', str(lines), '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Failed to retrieve logs: {result.stderr}"
        except Exception as e:
            return f"Error retrieving logs: {str(e)}"
    
    def send_email_alert(self, subject: str, body_text: str, body_html: str) -> bool:
        """Send email alert with retry logic"""
        if self.config['features']['dry_run']:
            self.logger.log('INFO', f"DRY RUN: Would send email - {subject}", self.correlation_id)
            return True
        
        smtp_config = self.config['smtp']
        attempts = self.config['monitoring']['retry_attempts']
        delay = self.config['monitoring']['retry_delay']
        
        for attempt in range(attempts):
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = smtp_config['from_address']
                msg['To'] = ', '.join(smtp_config['to_addresses'])
                
                msg.attach(MIMEText(body_text, 'plain'))
                msg.attach(MIMEText(body_html, 'html'))
                
                with smtplib.SMTP(smtp_config['server'], smtp_config['port'], 
                                 timeout=smtp_config['timeout']) as server:
                    if smtp_config['use_tls']:
                        server.starttls()
                    
                    if smtp_config['username'] and smtp_config['password']:
                        server.login(smtp_config['username'], smtp_config['password'])
                    
                    server.send_message(msg)
                
                self.logger.log('INFO', f"Email sent successfully: {subject}", self.correlation_id)
                return True
                
            except Exception as e:
                self.logger.log('ERROR', f"Email send attempt {attempt + 1} failed: {str(e)}", 
                              self.correlation_id)
                if attempt < attempts - 1:
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
        
        return False
    
    def create_alert_content(self, service_name: str, status: str, 
                           is_recovery: bool = False) -> Tuple[str, str, str]:
        """Create email alert content"""
        hostname = socket.gethostname()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if is_recovery:
            subject = f"[RECOVERY] {service_name} service restored on {hostname}"
            alert_type = "RECOVERY"
            alert_color = "#28a745"
        else:
            subject = f"[ALERT] {service_name} service down on {hostname}"
            alert_type = "FAILURE"
            alert_color = "#dc3545"
        
        # Get additional context
        stats = self.get_system_stats()
        logs = self.get_recent_logs(service_name)
        
        # Plain text version
        text_body = f"""
{alert_type} ALERT: {service_name} Service Monitoring

Timestamp: {timestamp}
Hostname: {hostname}
Service: {service_name}
Status: {status}

System Statistics:
- CPU Usage: {stats.get('cpu_usage', 'N/A')}%
- Memory Usage: {stats.get('memory_usage', 'N/A')}%
- Disk Usage: {stats.get('disk_usage', 'N/A')}

Recent Service Logs:
{logs}

---
This is an automated alert from Squid Monitor v{__version__}
        """
        
        # HTML version
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; color: #333; }}
        .header {{ background-color: {alert_color}; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .stats {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; }}
        .logs {{ background-color: #f1f1f1; padding: 15px; margin: 10px 0; 
                font-family: monospace; font-size: 12px; overflow-x: auto; }}
        .footer {{ color: #666; font-size: 12px; padding: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>{alert_type} ALERT: {service_name} Service</h2>
    </div>
    <div class="content">
        <p><strong>Timestamp:</strong> {timestamp}</p>
        <p><strong>Hostname:</strong> {hostname}</p>
        <p><strong>Service:</strong> {service_name}</p>
        <p><strong>Status:</strong> <code>{status}</code></p>
        
        <div class="stats">
            <h3>System Statistics</h3>
            <ul>
                <li>CPU Usage: {stats.get('cpu_usage', 'N/A')}%</li>
                <li>Memory Usage: {stats.get('memory_usage', 'N/A')}%</li>
                <li>Disk Usage: {stats.get('disk_usage', 'N/A')}</li>
            </ul>
        </div>
        
        <div class="logs">
            <h3>Recent Service Logs</h3>
            <pre>{logs}</pre>
        </div>
    </div>
    <div class="footer">
        <p>This is an automated alert from Squid Monitor v{__version__}</p>
    </div>
</body>
</html>
        """
        
        return subject, text_body, html_body
    
    def run_check(self) -> None:
        """Run a single monitoring check"""
        service_name = self.config['monitoring']['service_name']
        self.correlation_id = str(uuid.uuid4())
        
        self.logger.log('DEBUG', f"Starting service check for {service_name}", self.correlation_id)
        
        # Check service status
        is_active, status = self.check_service_status(service_name)
        
        # Determine if alert should be sent
        should_alert = self.state_manager.should_send_alert(
            is_active, 
            self.config['monitoring']['alert_cooldown']
        )
        
        if should_alert:
            is_recovery = is_active and self.state_manager.state['last_status'] is False
            subject, text_body, html_body = self.create_alert_content(
                service_name, status, is_recovery
            )
            
            # Send email alert
            email_sent = self.send_email_alert(subject, text_body, html_body)
            
            if not email_sent:
                self.logger.log('ERROR', "Failed to send email alert after all retries", 
                              self.correlation_id)
            
            # Send webhook if enabled
            if self.config['features']['enable_webhooks'] and self.config['features']['webhook_url']:
                self.send_webhook_alert(service_name, is_active, status)
            
            # Update state
            self.state_manager.update_state(is_active, alert_sent=email_sent)
        else:
            # Just update state
            self.state_manager.update_state(is_active, alert_sent=False)
        
        self.logger.log('INFO', 
                       f"Check complete - Service: {service_name}, Status: {status}, Alert sent: {should_alert}", 
                       self.correlation_id)
    
    def send_webhook_alert(self, service_name: str, is_active: bool, status: str) -> None:
        """Send webhook notification"""
        if self.config['features']['dry_run']:
            self.logger.log('INFO', "DRY RUN: Would send webhook", self.correlation_id)
            return
        
        try:
            import requests
            
            payload = {
                'service': service_name,
                'hostname': socket.gethostname(),
                'status': status,
                'is_active': is_active,
                'timestamp': datetime.now().isoformat(),
                'correlation_id': self.correlation_id
            }
            
            response = requests.post(
                self.config['features']['webhook_url'],
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.logger.log('INFO', "Webhook sent successfully", self.correlation_id)
            else:
                self.logger.log('ERROR', f"Webhook failed: {response.status_code}", self.correlation_id)
                
        except Exception as e:
            self.logger.log('ERROR', f"Webhook error: {str(e)}", self.correlation_id)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Squid Service Monitor - Monitor and alert on service status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Run with default configuration
  %(prog)s -c config.yaml     # Use custom config file
  %(prog)s --dry-run          # Test mode without sending alerts
  %(prog)s --once             # Run single check and exit
  %(prog)s --version          # Show version information
        """
    )
    
    parser.add_argument('-c', '--config', help='Configuration file path')
    parser.add_argument('--dry-run', action='store_true', help='Test mode - no alerts sent')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = Config(args.config)
        
        # Override with command line arguments
        if args.dry_run:
            config.config['features']['dry_run'] = True
        if args.debug:
            config.config['monitoring']['log_level'] = 'DEBUG'
        
        # Initialize components
        logger = Logger(config.config)
        state_manager = StateManager(config.config['monitoring']['state_file'])
        monitor = ServiceMonitor(config, logger, state_manager)
        
        # Log startup
        logger.log('INFO', f"Squid Monitor v{__version__} starting", str(uuid.uuid4()))
        
        # Run monitoring
        if args.once:
            monitor.run_check()
        else:
            # Continuous monitoring loop
            while True:
                try:
                    monitor.run_check()
                    time.sleep(config.config['monitoring']['check_interval'])
                except KeyboardInterrupt:
                    logger.log('INFO', "Monitor stopped by user", str(uuid.uuid4()))
                    break
                except Exception as e:
                    logger.log('ERROR', f"Unexpected error in main loop: {str(e)}", str(uuid.uuid4()))
                    time.sleep(60)  # Wait before retrying
        
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
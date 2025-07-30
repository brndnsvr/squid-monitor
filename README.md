# Squid Service Monitor

A production-ready monitoring solution for Squid proxy service with email alerting, state management, and extensive operational features.

## Features

- **Service Monitoring**: Automated monitoring of Squid service status using systemctl
- **Email Alerts**: SMTP-based email notifications with rich context
- **Alert Fatigue Prevention**: Intelligent state management to avoid alert spam
- **System Metrics**: CPU, memory, and disk usage included in alerts
- **Log Collection**: Recent service logs included in alert emails
- **Flexible Configuration**: YAML config files and environment variables
- **Container Ready**: Docker support with security hardening
- **Systemd Integration**: Timer-based scheduling for reliable execution
- **Structured Logging**: JSON-formatted logs with multiple outputs
- **Extensible Design**: Plugin architecture for future enhancements

## Quick Start

### System Requirements

- Python 3.7+ (for native installation)
- Docker (for containerized deployment)
- systemd (for service monitoring and scheduling)
- Linux operating system

### Installation

#### Option 1: Automated Setup (Recommended)

```bash
git clone https://github.com/brndnsvr/squid-monitor.git
cd squid-monitor
sudo ./setup.sh  # Interactive setup with configuration prompts
```

#### Option 2: Docker Deployment

```bash
git clone https://github.com/brndnsvr/squid-monitor.git
cd squid-monitor

# Configure your settings
cp .env.example .env
# Edit .env with your SMTP server details!
nano .env  # or use your preferred editor

# Start the monitor
docker-compose up -d

# View logs
docker logs -f squid-monitor
```

**Important for Docker:**
- You MUST configure your SMTP settings in the `.env` file
- Syslog is disabled in Docker (uses file logging only)
- To monitor host services, uncomment the systemd mounts in docker-compose.yml

#### Option 3: Manual Installation

See the [setup.sh](setup.sh) script for manual installation steps.

## Quick Usage

```bash
# Test configuration (dry run)
python3 src/squid_monitor.py --dry-run --once

# Run monitoring continuously
python3 src/squid_monitor.py

# Check service status
systemctl status squid-monitor.timer

# View logs
journalctl -u squid-monitor -f
```

## Configuration

### Configuration Methods

The monitor supports three configuration methods (in order of precedence):

1. **Environment Variables**
2. **YAML Configuration File**
3. **Default Values**

### Key Configuration Options

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| SMTP Server | `SMTP_SERVER` | smtp.example.com | SMTP relay server |
| SMTP Port | `SMTP_PORT` | 25 | SMTP server port |
| From Address | `SMTP_FROM` | squid-noreply@example.com | Sender email |
| To Addresses | `SMTP_TO` | admin@example.com | Recipients (comma-separated) |
| Service Name | `SERVICE_NAME` | squid | Service to monitor |
| Check Interval | `CHECK_INTERVAL` | 300 | Seconds between checks |
| Alert Cooldown | `ALERT_COOLDOWN` | 3600 | Seconds between repeat alerts |
| Log Level | `LOG_LEVEL` | INFO | Logging verbosity |

### Example Configuration File

```yaml
smtp:
  server: "mail.example.com"
  port: 587
  use_tls: true
  username: "monitor@example.com"
  password: "secure-password"
  from_address: "squid-monitor@example.com"
  to_addresses:
    - "ops-team@example.com"
    - "on-call@example.com"

monitoring:
  service_name: "squid"
  check_interval: 300
  alert_cooldown: 3600
  
features:
  enable_webhooks: true
  webhook_url: "https://monitoring.example.com/webhook"
```

## Command Line Options

```bash
squid_monitor.py [-h] [-c CONFIG] [--dry-run] [--once] [--debug] [--version]

Options:
  -h, --help            Show help message and exit
  -c CONFIG, --config CONFIG
                        Configuration file path
  --dry-run             Test mode - no alerts sent
  --once                Run once and exit
  --debug               Enable debug logging
  --version             Show version information
```

## Testing

```bash
# Run unit tests
./run_tests.sh

# Manual test with dry run
python3 src/squid_monitor.py --dry-run --once
```

## Alert Examples

### Failure Alert
- Subject: `[ALERT] squid service down on server01`
- Includes: Timestamp, hostname, service status, system metrics, recent logs

### Recovery Alert
- Subject: `[RECOVERY] squid service restored on server01`
- Confirms service restoration with current system state

## Security Considerations

1. **Least Privilege**: Runs as non-root user `squid-monitor`
2. **Systemd Hardening**: Extensive security options in service unit
3. **No Hardcoded Secrets**: All credentials via environment/config
4. **Input Validation**: Email addresses and configuration validated
5. **TLS Support**: Optional SMTP encryption
6. **Container Security**: Non-root container with minimal attack surface

## Monitoring Integration

### Prometheus Metrics (Future)
The monitor is designed to expose metrics at `/metrics` endpoint (plugin required).

### Webhook Support
Enable webhooks to integrate with external monitoring systems:
```yaml
features:
  enable_webhooks: true
  webhook_url: "https://your-monitoring-system.com/webhook"
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions to common issues including:

- Python "externally-managed-environment" errors
- Permission denied errors
- Docker/container issues
- SMTP configuration problems
- Platform-specific issues (macOS, etc.)

### Quick Fixes

**Python Installation Issues:**
```bash
# Option 1: Use system packages
sudo apt install -y python3-yaml python3-requests

# Option 2: Use virtual environment
sudo python3 -m venv /opt/squid-monitor/venv
sudo /opt/squid-monitor/venv/bin/pip install -r requirements.txt
```

**Testing Without Installation:**
```bash
# Local test (no sudo required)
./test-local.sh
```

## Development

### Project Structure
```
squid-monitor/
├── src/
│   └── squid_monitor.py      # Main monitoring script
├── tests/
│   └── test_squid_monitor.py # Unit tests
├── config/
│   └── config.example.yaml   # Example configuration
├── systemd/
│   ├── squid-monitor.service # Systemd service unit
│   ├── squid-monitor.timer   # Systemd timer unit
│   └── squid-monitor.env.example
├── Dockerfile                # Container image
├── docker-compose.yml        # Docker Compose config
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

### Adding Features

1. **New Check Types**: Implement in `ServiceMonitor` class
2. **Additional Alerts**: Extend `send_webhook_alert()` method
3. **New Config Options**: Update `Config` class and documentation

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details

## Support

- Issues: https://github.com/brndnsvr/squid-monitor/issues
- Documentation: https://github.com/brndnsvr/squid-monitor/wiki
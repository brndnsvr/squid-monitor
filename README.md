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

#### Option 1: Native Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/squid-monitor.git
cd squid-monitor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create necessary directories:
```bash
sudo mkdir -p /var/lib/squid-monitor /var/log/squid-monitor /etc/squid-monitor
sudo useradd -r -s /bin/false squid-monitor
sudo chown squid-monitor:squid-monitor /var/lib/squid-monitor /var/log/squid-monitor
```

4. Copy configuration:
```bash
sudo cp config/config.example.yaml /etc/squid-monitor/config.yaml
sudo cp systemd/squid-monitor.env.example /etc/squid-monitor/squid-monitor.env
# Edit the files with your settings
```

5. Install systemd units:
```bash
sudo cp systemd/squid-monitor.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable squid-monitor.timer
sudo systemctl start squid-monitor.timer
```

#### Option 2: Docker Deployment

1. Clone the repository:
```bash
git clone https://github.com/yourusername/squid-monitor.git
cd squid-monitor
```

2. Build the image:
```bash
docker build -t squid-monitor:latest .
```

3. Run with docker-compose:
```bash
# Edit docker-compose.yml with your settings
docker-compose up -d
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

## Usage

### Command Line Options

```bash
# Run with default configuration
python3 squid_monitor.py

# Use custom config file
python3 squid_monitor.py -c /path/to/config.yaml

# Run once and exit
python3 squid_monitor.py --once

# Dry run mode (no alerts sent)
python3 squid_monitor.py --dry-run

# Enable debug logging
python3 squid_monitor.py --debug

# Show version
python3 squid_monitor.py --version
```

### Testing

Run the test suite:
```bash
cd squid-monitor
python -m pytest tests/ -v
```

Run a single test check:
```bash
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

### Common Issues

1. **Permission Denied**
   - Ensure squid-monitor user has required permissions
   - Check systemd security restrictions

2. **Email Not Sending**
   - Verify SMTP server connectivity: `telnet smtp-server 25`
   - Check firewall rules
   - Enable debug logging to see SMTP conversation

3. **Service Check Fails**
   - Verify systemctl access: `sudo -u squid-monitor systemctl is-active squid`
   - Check if running in container (may need host PID namespace)

4. **State File Issues**
   - Ensure write permissions on state directory
   - Check disk space

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python3 squid_monitor.py --debug
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

[Your License Here]

## Support

- Issues: https://github.com/yourusername/squid-monitor/issues
- Documentation: https://github.com/yourusername/squid-monitor/wiki
#!/bin/bash
# Quick configuration script for Docker/manual setup

echo "Squid Monitor Configuration"
echo "=========================="

# Prompt for configuration
read -p "Enter SMTP server address [smtp.example.com]: " smtp_server
smtp_server=${smtp_server:-smtp.example.com}

read -p "Enter SMTP port [25]: " smtp_port
smtp_port=${smtp_port:-25}

read -p "Enable TLS? (y/n) [n]: " use_tls
use_tls=${use_tls:-n}
if [[ "$use_tls" == "y" ]]; then
    use_tls="true"
else
    use_tls="false"
fi

read -p "Enter sender email address [squid-monitor@example.com]: " from_email
from_email=${from_email:-squid-monitor@example.com}

read -p "Enter recipient email address [admin@example.com]: " to_email
to_email=${to_email:-admin@example.com}

read -p "Enter service name to monitor [squid]: " service_name
service_name=${service_name:-squid}

# Create .env file for Docker
cat > .env <<EOF
# Squid Monitor Configuration
SMTP_SERVER=$smtp_server
SMTP_PORT=$smtp_port
SMTP_USE_TLS=$use_tls
SMTP_FROM=$from_email
SMTP_TO=$to_email
SERVICE_NAME=$service_name
EOF

# Create config.yaml
mkdir -p config
cat > config/config.yaml <<EOF
# Squid Monitor Configuration
smtp:
  server: "$smtp_server"
  port: $smtp_port
  use_tls: $use_tls
  from_address: "$from_email"
  to_addresses:
    - "$to_email"

monitoring:
  service_name: "$service_name"
  check_interval: 300
  alert_cooldown: 3600
  state_file: "/var/lib/squid-monitor/state.json"
  log_file: "/var/log/squid-monitor/monitor.log"
  log_level: "INFO"

features:
  dry_run: false
  enable_syslog: true
  enable_webhooks: false
EOF

echo ""
echo "Configuration saved to:"
echo "  - .env (for Docker)"
echo "  - config/config.yaml"
echo ""
echo "To test: python3 src/squid_monitor.py --dry-run --once"
echo "To run with Docker: docker-compose up -d"
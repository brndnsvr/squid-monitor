#!/bin/bash
# Squid Monitor Setup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/squid-monitor"
CONFIG_DIR="/etc/squid-monitor"
STATE_DIR="/var/lib/squid-monitor"
LOG_DIR="/var/log/squid-monitor"
SERVICE_USER="squid-monitor"

echo -e "${GREEN}Squid Monitor Setup Script${NC}"
echo "================================"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Check system requirements
echo -e "\n${YELLOW}Checking system requirements...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed${NC}"
    exit 1
fi

if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}systemd is required but not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ System requirements met${NC}"

# Create user
echo -e "\n${YELLOW}Creating service user...${NC}"
if ! id "$SERVICE_USER" &> /dev/null; then
    useradd -r -s /bin/false -d "$STATE_DIR" -c "Squid Monitor Service" "$SERVICE_USER"
    echo -e "${GREEN}✓ Created user: $SERVICE_USER${NC}"
else
    echo -e "${GREEN}✓ User already exists: $SERVICE_USER${NC}"
fi

# Create directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"/{src,config} "$CONFIG_DIR" "$STATE_DIR" "$LOG_DIR"
echo -e "${GREEN}✓ Directories created${NC}"

# Copy files
echo -e "\n${YELLOW}Installing files...${NC}"
cp -r src/* "$INSTALL_DIR/src/"
cp config/config.example.yaml "$CONFIG_DIR/config.example.yaml"
cp systemd/squid-monitor.env.example "$CONFIG_DIR/squid-monitor.env.example"

if [[ ! -f "$CONFIG_DIR/config.yaml" ]]; then
    cp "$CONFIG_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
    echo -e "${YELLOW}  Created default config at $CONFIG_DIR/config.yaml${NC}"
fi

if [[ ! -f "$CONFIG_DIR/squid-monitor.env" ]]; then
    cp "$CONFIG_DIR/squid-monitor.env.example" "$CONFIG_DIR/squid-monitor.env"
    echo -e "${YELLOW}  Created default env file at $CONFIG_DIR/squid-monitor.env${NC}"
fi

# Install Python dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"

# Check if we need to use system packages or venv
if python3 -m pip install --help 2>&1 | grep -q "externally-managed-environment"; then
    echo -e "${YELLOW}Detected externally managed Python environment${NC}"
    
    # Try to install system packages first
    echo "Attempting to install system packages..."
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y python3-yaml python3-requests || {
            echo -e "${YELLOW}System packages not sufficient, creating virtual environment...${NC}"
            VENV_NEEDED=true
        }
    else
        VENV_NEEDED=true
    fi
    
    if [[ "$VENV_NEEDED" == "true" ]]; then
        # Create a virtual environment
        python3 -m venv "$INSTALL_DIR/venv"
        source "$INSTALL_DIR/venv/bin/activate"
        pip install -r requirements.txt
        deactivate
        
        # Update the Python path in service file
        PYTHON_BIN="$INSTALL_DIR/venv/bin/python3"
        echo -e "${YELLOW}Using virtual environment at $INSTALL_DIR/venv${NC}"
    else
        PYTHON_BIN="/usr/bin/python3"
    fi
else
    # Traditional pip install
    pip3 install -r requirements.txt
    PYTHON_BIN="/usr/bin/python3"
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Set permissions
echo -e "\n${YELLOW}Setting permissions...${NC}"
chown -R "$SERVICE_USER:$SERVICE_USER" "$STATE_DIR" "$LOG_DIR"
chown -R root:root "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR/src/squid_monitor.py"
chmod 600 "$CONFIG_DIR"/*.yaml "$CONFIG_DIR"/*.env
echo -e "${GREEN}✓ Permissions set${NC}"

# Install systemd units
echo -e "\n${YELLOW}Installing systemd units...${NC}"
cp systemd/squid-monitor.service /etc/systemd/system/
cp systemd/squid-monitor.timer /etc/systemd/system/

# Update paths in service file
sed -i "s|/opt/squid-monitor|$INSTALL_DIR|g" /etc/systemd/system/squid-monitor.service
sed -i "s|/usr/bin/python3|$PYTHON_BIN|g" /etc/systemd/system/squid-monitor.service

systemctl daemon-reload
echo -e "${GREEN}✓ Systemd units installed${NC}"

# Interactive configuration
echo -e "\n${YELLOW}Configuration Setup${NC}"
echo "===================="

# Function to update config value
update_config() {
    local key=$1
    local value=$2
    local file=$3
    
    if [[ "$file" == *.yaml ]]; then
        # For YAML files, this is simplified - in production you'd use yq or similar
        sed -i "s|$key:.*|$key: \"$value\"|g" "$file"
    else
        # For env files
        sed -i "s|^$key=.*|$key=$value|g" "$file"
    fi
}

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

# Update configuration files
echo -e "\n${YELLOW}Updating configuration files...${NC}"

# Update env file
update_config "SMTP_SERVER" "$smtp_server" "$CONFIG_DIR/squid-monitor.env"
update_config "SMTP_PORT" "$smtp_port" "$CONFIG_DIR/squid-monitor.env"
update_config "SMTP_USE_TLS" "$use_tls" "$CONFIG_DIR/squid-monitor.env"
update_config "SMTP_FROM" "$from_email" "$CONFIG_DIR/squid-monitor.env"
update_config "SMTP_TO" "$to_email" "$CONFIG_DIR/squid-monitor.env"
update_config "SERVICE_NAME" "$service_name" "$CONFIG_DIR/squid-monitor.env"

# Also update the YAML config
sed -i "s|server:.*|server: \"$smtp_server\"|g" "$CONFIG_DIR/config.yaml"
sed -i "s|port:.*|port: $smtp_port|g" "$CONFIG_DIR/config.yaml"
sed -i "s|use_tls:.*|use_tls: $use_tls|g" "$CONFIG_DIR/config.yaml"
sed -i "s|from_address:.*|from_address: \"$from_email\"|g" "$CONFIG_DIR/config.yaml"
sed -i "/to_addresses:/,/^[^ ]/{s|- .*|- \"$to_email\"/}" "$CONFIG_DIR/config.yaml"
sed -i "s|service_name:.*|service_name: \"$service_name\"|g" "$CONFIG_DIR/config.yaml"

echo -e "${GREEN}✓ Configuration updated${NC}"

# Test configuration
echo -e "\n${YELLOW}Testing configuration...${NC}"
if $PYTHON_BIN $INSTALL_DIR/src/squid_monitor.py --dry-run --once; then
    echo -e "${GREEN}✓ Configuration test passed${NC}"
else
    echo -e "${RED}✗ Configuration test failed. Please check the settings.${NC}"
fi

# Configuration reminder
echo -e "\n${YELLOW}Next Steps:${NC}"
echo "1. Review configuration:"
echo "   - $CONFIG_DIR/config.yaml"
echo "   - $CONFIG_DIR/squid-monitor.env"
echo ""
echo "2. Enable and start the timer:"
echo "   systemctl enable squid-monitor.timer"
echo "   systemctl start squid-monitor.timer"
echo ""
echo "3. Check status:"
echo "   systemctl status squid-monitor.timer"
echo "   journalctl -u squid-monitor -f"

echo -e "\n${GREEN}Setup complete!${NC}"
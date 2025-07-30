# Squid Monitor Troubleshooting Guide

## Common Installation Issues

### 1. Python "externally-managed-environment" Error

**Error:**
```
error: externally-managed-environment
× This environment is externally managed
```

**Cause:** Modern Debian 12+ and Ubuntu 23.04+ systems prevent system-wide pip installations (PEP 668).

**Solutions:**

#### Option A: Use System Packages (Recommended)
```bash
sudo apt update
sudo apt install -y python3-yaml python3-requests
```

#### Option B: Create Virtual Environment
```bash
# Install venv support
sudo apt install -y python3-venv

# Create virtual environment
sudo python3 -m venv /opt/squid-monitor/venv

# Install dependencies
sudo /opt/squid-monitor/venv/bin/pip install -r requirements.txt

# Update systemd service to use venv Python
sudo sed -i 's|/usr/bin/python3|/opt/squid-monitor/venv/bin/python3|g' /etc/systemd/system/squid-monitor.service
sudo systemctl daemon-reload
```

#### Option C: Force System-Wide Install (Not Recommended)
```bash
sudo pip3 install --break-system-packages -r requirements.txt
```

### 2. Permission Denied Errors

**Error:**
```
Fatal error: [Errno 13] Permission denied: '/var/log/squid-monitor/monitor.log'
```

**Solutions:**

#### For Testing:
```bash
# Use the local test script (no sudo required)
./test-local.sh
```

#### For Production:
```bash
# Ensure directories exist with correct permissions
sudo mkdir -p /var/lib/squid-monitor /var/log/squid-monitor
sudo chown -R squid-monitor:squid-monitor /var/lib/squid-monitor /var/log/squid-monitor
```

### 3. systemctl Not Working in Docker

**Error:**
```
Running in chroot, ignoring command 'is-active'
```

**Cause:** Docker containers don't have full systemd access.

**Solutions:**
- Run the monitor directly on the host system (recommended)
- Use the native installation instead of Docker for production
- Docker is best suited for testing the alerting logic, not actual service monitoring

### 4. No systemctl on macOS

**Error:**
```
command not found: systemctl
```

**Cause:** macOS doesn't use systemd.

**Solution:** This tool is designed for Linux systems. To test on macOS:
```bash
# Use local test mode
./test-local.sh

# Or use Docker for testing
docker-compose up
```

## Common Runtime Issues

### 1. SMTP Connection Failed

**Error:**
```
socket.gaierror: [Errno -2] Name or service not known
```

**Solutions:**
- Verify SMTP server address in configuration
- Check network connectivity: `telnet smtp.server.com 25`
- Ensure firewall allows outbound SMTP connections

### 2. Service Check Always Shows Empty Status

**Symptoms:** Logs show `Status: , Alert sent: False`

**Solutions:**
- Verify you're running on a Linux system with systemd
- Check if the service name is correct: `systemctl list-units | grep squid`
- Ensure the monitor has permission to run systemctl

### 3. Not Receiving Email Alerts

**Checklist:**
1. Verify `DRY_RUN=false` in configuration
2. Check SMTP settings are correct
3. Look for email errors in logs: `grep ERROR /var/log/squid-monitor/monitor.log`
4. Test SMTP manually:
   ```python
   python3 -c "import smtplib; s = smtplib.SMTP('your.smtp.server', 25); s.quit(); print('SMTP OK')"
   ```

## Configuration Issues

### 1. Configuration Not Loading

**Solutions:**
- Check file paths in environment variables
- Verify YAML syntax: `python3 -m yaml config/config.yaml`
- Use debug mode: `LOG_LEVEL=DEBUG`

### 2. Environment Variables Not Working

**Common Mistakes:**
- Forgetting to export variables: use `export VAR=value`
- Wrong variable names (check spelling)
- For systemd, put variables in `/etc/squid-monitor/squid-monitor.env`

## Debugging Tips

### 1. Enable Debug Logging
```bash
export LOG_LEVEL=DEBUG
python3 src/squid_monitor.py --once
```

### 2. Check Logs
```bash
# System logs
sudo journalctl -u squid-monitor -f

# Application logs
tail -f /var/log/squid-monitor/monitor.log

# For JSON logs, pretty print
tail -f /var/log/squid-monitor/monitor.log | jq '.'
```

### 3. Test Individual Components

Test service check:
```bash
systemctl is-active squid
echo "Exit code: $?"
```

Test state file:
```bash
cat /var/lib/squid-monitor/state.json | jq '.'
```

### 4. Manual Test Run
```bash
# Dry run with debug
sudo LOG_LEVEL=DEBUG DRY_RUN=true python3 /opt/squid-monitor/src/squid_monitor.py --once
```

## Getting Help

If these solutions don't resolve your issue:

1. Check existing issues: https://github.com/brndnsvr/squid-monitor/issues
2. Create a new issue with:
   - Your OS version
   - Python version (`python3 --version`)
   - Full error message
   - Steps to reproduce
   - Relevant log entries
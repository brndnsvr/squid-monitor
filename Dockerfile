FROM python:3.9-slim

LABEL maintainer="maintainer@example.com"
LABEL description="Squid Service Monitor - Production-ready monitoring for Squid proxy"
LABEL version="1.0.0"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    systemd \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r squid-monitor && useradd -r -g squid-monitor squid-monitor

# Create necessary directories
RUN mkdir -p /opt/squid-monitor/src \
             /opt/squid-monitor/config \
             /var/lib/squid-monitor \
             /var/log/squid-monitor \
             /etc/squid-monitor

# Set ownership
RUN chown -R squid-monitor:squid-monitor /var/lib/squid-monitor /var/log/squid-monitor

# Copy application files
COPY --chown=squid-monitor:squid-monitor src/squid_monitor.py /opt/squid-monitor/src/
COPY --chown=squid-monitor:squid-monitor config/config.example.yaml /opt/squid-monitor/config/
COPY --chown=squid-monitor:squid-monitor requirements.txt /opt/squid-monitor/

# Install Python dependencies
WORKDIR /opt/squid-monitor
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER squid-monitor

# Set environment variables
ENV PYTHONPATH=/opt/squid-monitor/src
ENV STATE_FILE=/var/lib/squid-monitor/state.json
ENV LOG_FILE=/var/log/squid-monitor/monitor.log

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python3 /opt/squid-monitor/src/squid_monitor.py --dry-run --once || exit 1

# Default command - run in continuous mode
CMD ["python3", "/opt/squid-monitor/src/squid_monitor.py"]
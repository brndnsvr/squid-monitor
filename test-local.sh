#!/bin/bash
# Test script that uses local directories

# Set environment variables to use local paths
export LOG_FILE="./logs/monitor.log"
export STATE_FILE="./state/state.json"
export DRY_RUN=true
export LOG_LEVEL=INFO

# Create local directories
mkdir -p logs state

# Run the monitor
python3 src/squid_monitor.py --once
#!/bin/bash
# Run tests for Squid Monitor

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "Running Squid Monitor Tests"
echo "=========================="

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Run unit tests
echo -e "\n${GREEN}Running unit tests...${NC}"
python3 -m pytest tests/test_squid_monitor.py -v --tb=short

# Run coverage if available
if command -v coverage &> /dev/null; then
    echo -e "\n${GREEN}Running coverage analysis...${NC}"
    coverage run -m pytest tests/test_squid_monitor.py
    coverage report -m --include="src/*"
fi

# Run integration test
echo -e "\n${GREEN}Running dry-run integration test...${NC}"
export DRY_RUN=true
export LOG_LEVEL=INFO
python3 src/squid_monitor.py --once --dry-run

echo -e "\n${GREEN}All tests passed!${NC}"
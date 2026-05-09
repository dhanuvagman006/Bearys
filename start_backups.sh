#!/bin/bash

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================"
echo "Starting Backup Servers..."
echo "========================================"

# Check if a virtual environment is activated, if not, try to use the local venv
if [[ -z "$VIRTUAL_ENV" ]]; then
    if [ -f "venv/bin/activate" ]; then
        echo "Activating virtual environment..."
        source venv/bin/activate
    else
        echo "Warning: No virtual environment detected. Using system Python."
    fi
fi

# Start Server 1
echo "-> Starting Backup Server 1 (Port 8000)..."
nohup python backup_servers/server_1/backup_server.py > backup_server_1.log 2>&1 &
PID1=$!
echo "   [Started] PID: $PID1"

# Start Server 2
echo "-> Starting Backup Server 2 (Port 8001)..."
nohup python backup_servers/server_2/backup_server.py > backup_server_2.log 2>&1 &
PID2=$!
echo "   [Started] PID: $PID2"

echo "========================================"
echo "All backup servers are running in the background."
echo "Logs are being written to:"
echo " - backup_server_1.log"
echo " - backup_server_2.log"
echo ""
echo "To stop the servers, run the following command:"
echo "kill $PID1 $PID2"
echo "========================================"

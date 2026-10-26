#!/bin/bash
# ==============================================================================
# InkYard - macOS Startup Script
# ==============================================================================

set -e

cd "$(dirname "$0")"

echo "================================================================="
echo "   Starting InkYard Portal (macOS Local Host)"
echo "================================================================="

# Find local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

# Check if port 5000 is taken (e.g. by AirPlay Receiver)
if lsof -i :5000 >/dev/null 2>&1; then
    PORT=5050
else
    PORT=5000
fi
export PORT

echo "   Localhost:  http://localhost:${PORT}"
echo "   School/LAN: http://${LOCAL_IP}:${PORT}"
echo "   Printer:    Canon Multifunction @ 172.16.4.9"
echo "-----------------------------------------------------------------"
echo "  Students on iPad, Mac, and Windows can open: http://${LOCAL_IP}:${PORT}"
echo "================================================================="

# Open browser automatically after 1.2 seconds in background
(sleep 1.2 && open "http://localhost:${PORT}") &

# Run server with caffeinate to prevent macOS from sleeping when idle or running on battery/AC
echo "   Caffeinate active: Mac will stay awake while server is running."
echo "================================================================="
if command -v caffeinate >/dev/null 2>&1; then
    exec caffeinate -dimsu python3 server.py
else
    exec python3 server.py
fi


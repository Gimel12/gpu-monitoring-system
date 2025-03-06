#!/bin/bash

# GPU Monitor Cockpit Plugin Installer
# This script installs the GPU Monitor plugin for Cockpit

set -e

echo "Installing GPU Monitor Cockpit Plugin..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# Check if Cockpit is installed
if ! command -v cockpit-bridge &> /dev/null; then
  echo "Cockpit is not installed. Please install it first."
  echo "On RHEL/CentOS/Fedora: sudo dnf install cockpit"
  echo "On Ubuntu/Debian: sudo apt install cockpit"
  exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PLUGIN_DIR="$SCRIPT_DIR/gpu-monitor"

# Create the Cockpit package directory if it doesn't exist
COCKPIT_DIR="/usr/share/cockpit/gpu-monitor"
mkdir -p "$COCKPIT_DIR"

# Copy the plugin files
echo "Copying plugin files to $COCKPIT_DIR..."
cp -r "$PLUGIN_DIR"/* "$COCKPIT_DIR/"

# Make the bridge script executable
chmod +x "$COCKPIT_DIR/cockpit-bridge.py"

# Create a systemd service for the bridge
cat > /etc/systemd/system/gpu-monitor-bridge.service << EOF
[Unit]
Description=GPU Monitor Cockpit Bridge
After=network.target

[Service]
ExecStart=/usr/share/cockpit/gpu-monitor/cockpit-bridge.py
Restart=always
User=root
Group=root
Environment=PATH=/usr/bin:/usr/local/bin
WorkingDirectory=/usr/share/cockpit/gpu-monitor

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Start and enable the service
echo "Starting GPU Monitor bridge service..."
systemctl start gpu-monitor-bridge
systemctl enable gpu-monitor-bridge

echo "Installation complete!"
echo "Please restart Cockpit: systemctl restart cockpit"
echo "Then access the GPU Monitor tab in the Cockpit web interface."

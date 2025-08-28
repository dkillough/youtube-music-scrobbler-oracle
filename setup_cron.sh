#!/bin/bash
# Set up cron job for YTMusic Scrobbler

set -e

SERVICE_DIR="/opt/ytmusic-scrobbler"
SERVICE_USER="ytmusic"
DEFAULT_INTERVAL=5  # Default to 5 minutes

# Get interval from command line argument or use default
INTERVAL_MINUTES=${1:-$DEFAULT_INTERVAL}

# Validate interval
if ! [[ "$INTERVAL_MINUTES" =~ ^[0-9]+$ ]] || [ "$INTERVAL_MINUTES" -lt 1 ]; then
    echo "❌ Invalid interval: $INTERVAL_MINUTES"
    echo "Usage: $0 [interval_minutes]"
    echo "Example: $0 5  # Run every 5 minutes"
    exit 1
fi

echo "⏰ Setting up cron job to run every $INTERVAL_MINUTES minutes..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Check if service directory exists
if [ ! -d "$SERVICE_DIR" ]; then
    echo "❌ Service directory $SERVICE_DIR not found. Please run deploy.sh first."
    exit 1
fi

# Check if service user exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "❌ Service user $SERVICE_USER not found. Please run deploy.sh first."
    exit 1
fi

# Create cron schedule based on interval
if [ "$INTERVAL_MINUTES" -eq 1 ]; then
    CRON_SCHEDULE="* * * * *"
elif [ "$INTERVAL_MINUTES" -lt 60 ]; then
    CRON_SCHEDULE="*/$INTERVAL_MINUTES * * * *"
else
    HOUR_INTERVAL=$((INTERVAL_MINUTES / 60))
    CRON_SCHEDULE="0 */$HOUR_INTERVAL * * *"
fi

# Create the cron command
CRON_COMMAND="$SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py"

# Create temporary cron file
TEMP_CRON=$(mktemp)

# Get existing crontab for the service user (if any)
sudo -u "$SERVICE_USER" crontab -l 2>/dev/null > "$TEMP_CRON" || true

# Remove any existing ytmusic-scrobbler entries
grep -v "ytmusic-scrobbler" "$TEMP_CRON" > "${TEMP_CRON}.new" || true
mv "${TEMP_CRON}.new" "$TEMP_CRON"

# Add new cron entry
echo "# YTMusic Scrobbler - runs every $INTERVAL_MINUTES minutes" >> "$TEMP_CRON"
echo "$CRON_SCHEDULE $CRON_COMMAND # ytmusic-scrobbler" >> "$TEMP_CRON"

# Install the new crontab
sudo -u "$SERVICE_USER" crontab "$TEMP_CRON"

# Clean up
rm "$TEMP_CRON"

echo "✅ Cron job installed successfully!"
echo "📅 Schedule: Every $INTERVAL_MINUTES minutes ($CRON_SCHEDULE)"
echo "👤 Running as: $SERVICE_USER"
echo "🔧 Command: $CRON_COMMAND"
echo ""
echo "📋 Useful commands:"
echo "  View cron jobs: sudo -u $SERVICE_USER crontab -l"
echo "  View logs: sudo -u $SERVICE_USER tail -f $SERVICE_DIR/config/scrobble.log"
echo "  Remove cron job: sudo -u $SERVICE_USER crontab -e  # then delete the ytmusic-scrobbler line"
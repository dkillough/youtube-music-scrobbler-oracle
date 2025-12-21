#!/bin/bash
# Cron setup script for YTMusic Scrobbler

if [ $# -eq 0 ]; then
    echo "Usage: $0 <interval_minutes>"
    echo "Example: $0 120   # Run every 2 hours (recommended for mobile gap-filling)"
    echo "Example: $0 180   # Run every 3 hours"
    echo "Example: $0 240   # Run every 4 hours"
    exit 1
fi

INTERVAL=$1
SERVICE_DIR="/opt/ytmusic-scrobbler"
SERVICE_USER="ytmusic"

# Validate interval
if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [ "$INTERVAL" -lt 1 ] || [ "$INTERVAL" -gt 1440 ]; then
    echo "❌ Invalid interval. Must be a number between 1 and 1440 minutes."
    exit 1
fi

echo "⏰ Setting up cron job to run every $INTERVAL minutes..."

# Calculate cron expression based on interval
if [ "$INTERVAL" -lt 60 ]; then
    # Less than an hour - use minute interval
    CRON_EXPR="*/$INTERVAL * * * *"
elif [ "$INTERVAL" -eq 60 ]; then
    # Exactly one hour
    CRON_EXPR="0 * * * *"
else
    # Multiple hours
    HOUR_INTERVAL=$((INTERVAL / 60))
    MINUTE_REMAINDER=$((INTERVAL % 60))

    if [ "$MINUTE_REMAINDER" -eq 0 ]; then
        CRON_EXPR="0 */$HOUR_INTERVAL * * *"
    else
        # For non-whole hours, fall back to minute-based expression
        CRON_EXPR="*/$INTERVAL * * * *"
    fi
fi

# Add to user's crontab
(sudo -u "$SERVICE_USER" crontab -l 2>/dev/null | grep -v "$SERVICE_DIR/scrobble_oracle.py"; echo "$CRON_EXPR $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py >> $SERVICE_DIR/config/scrobble.log 2>&1") | sudo -u "$SERVICE_USER" crontab -

echo "✅ Cron job configured successfully!"
echo "📋 Current crontab for $SERVICE_USER:"
sudo -u "$SERVICE_USER" crontab -l

echo ""
echo "🔧 Management commands:"
echo "  View logs:     sudo -u $SERVICE_USER tail -f $SERVICE_DIR/config/scrobble.log"
echo "  Manual run:    sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py"
echo "  Dry run:       sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py --dry-run"
echo "  View history:  sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/history_manager.py stats"

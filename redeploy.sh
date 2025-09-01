#!/bin/bash
# Redeploy YTMusic Scrobbler on Oracle Cloud while preserving history
# Usage: sudo bash redeploy.sh [cron_interval_minutes]

set -e

SERVICE_DIR="/opt/ytmusic-scrobbler"
SERVICE_USER="ytmusic"
BACKUP_DIR="/tmp/ytmusic-backup-$(date +%Y%m%d_%H%M%S)"
DEFAULT_CRON_INTERVAL=120  # 2 hours default

# Get cron interval from argument or use default
CRON_INTERVAL=${1:-$DEFAULT_CRON_INTERVAL}

echo "🔄 Starting YTMusic Scrobbler redeployment..."
echo "   Service directory: $SERVICE_DIR"
echo "   Backup location: $BACKUP_DIR"
echo "   Cron interval: $CRON_INTERVAL minutes"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Validate service directory exists
if [ ! -d "$SERVICE_DIR" ]; then
    echo "❌ Service directory not found: $SERVICE_DIR"
    echo "   Run the initial deployment script first"
    exit 1
fi

# Step 1: Backup existing configuration and history
echo "💾 Creating backup..."
if [ -d "$SERVICE_DIR/config" ]; then
    cp -r "$SERVICE_DIR/config" "$BACKUP_DIR"
    echo "   ✅ Backed up config to: $BACKUP_DIR"
else
    echo "   ⚠️  No existing config directory found"
    mkdir -p "$BACKUP_DIR"
fi

# Step 2: Stop current cron job
echo "⏹️  Stopping current cron job..."
if sudo -u "$SERVICE_USER" crontab -l 2>/dev/null | grep -q "scrobble_oracle.py"; then
    # Remove existing cron job
    sudo -u "$SERVICE_USER" crontab -l 2>/dev/null | grep -v "scrobble_oracle.py" | sudo -u "$SERVICE_USER" crontab -
    echo "   ✅ Removed existing cron job"
else
    echo "   ℹ️  No existing cron job found"
fi

# Step 3: Update code
echo "📦 Updating code..."
cd "$SERVICE_DIR"

# Check if it's a git repository
if [ -d ".git" ]; then
    echo "   Using git to update..."
    sudo -u "$SERVICE_USER" git pull origin main
    echo "   ✅ Code updated from git"
else
    echo "   ⚠️  Not a git repository - manual file updates required"
    echo "   Please copy your updated files to: $SERVICE_DIR"
    read -p "Press Enter after copying files to continue..."
fi

# Step 4: Update dependencies
echo "🔧 Updating dependencies..."
if [ -f "requirements.txt" ]; then
    sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install -r requirements.txt
    echo "   ✅ Dependencies updated"
else
    echo "   ⚠️  No requirements.txt found"
fi

# Step 5: Restore configuration and history
echo "🔙 Restoring configuration and history..."
if [ -d "$BACKUP_DIR" ]; then
    # Ensure config directory exists
    mkdir -p "$SERVICE_DIR/config"
    
    # Copy backed up files
    cp -r "$BACKUP_DIR"/* "$SERVICE_DIR/config/"
    
    # Fix ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR/config"
    
    echo "   ✅ Configuration and history restored"
    
    # Show what was restored
    echo "   📁 Restored files:"
    ls -la "$SERVICE_DIR/config/"
    
    # Verify history preservation
    echo "🔍 Verifying preserved history..."
    if [ -f "$SERVICE_DIR/config/scrobble_history.json" ]; then
        HISTORY_COUNT=$(sudo -u "$SERVICE_USER" python3 -c "
import json
try:
    with open('$SERVICE_DIR/config/scrobble_history.json', 'r') as f:
        data = json.load(f)
    print(len(data))
except:
    print(0)
" 2>/dev/null)
        echo "   ✅ Scrobble history preserved: $HISTORY_COUNT entries"
    else
        echo "   ℹ️  No scrobble history file found (starting fresh)"
    fi
    
    if [ -f "$SERVICE_DIR/config/history.txt" ]; then
        LEGACY_ID=$(cat "$SERVICE_DIR/config/history.txt" 2>/dev/null || echo "none")
        echo "   ✅ Legacy history preserved: last track ID $LEGACY_ID"
    else
        echo "   ℹ️  No legacy history file found"
    fi
    
    if [ -f "$SERVICE_DIR/config/browser.json" ]; then
        echo "   ✅ YouTube Music credentials preserved"
    else
        echo "   ⚠️  No browser.json found - you'll need to reconfigure credentials"
    fi
else
    echo "   ❌ Backup directory not found: $BACKUP_DIR"
    exit 1
fi

# Step 6: Setup new cron job with specified interval
echo "⏰ Setting up cron job (every $CRON_INTERVAL minutes)..."

# Calculate cron expression based on interval
if [ "$CRON_INTERVAL" -lt 60 ]; then
    # Less than an hour - use minute interval
    CRON_EXPR="*/$CRON_INTERVAL * * * *"
elif [ "$CRON_INTERVAL" -eq 60 ]; then
    # Exactly one hour
    CRON_EXPR="0 * * * *"
else
    # Multiple hours
    HOUR_INTERVAL=$((CRON_INTERVAL / 60))
    CRON_EXPR="0 */$HOUR_INTERVAL * * *"
fi

# Add new cron job
(sudo -u "$SERVICE_USER" crontab -l 2>/dev/null || true; echo "$CRON_EXPR $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py # ytmusic-scrobbler") | sudo -u "$SERVICE_USER" crontab -

echo "   ✅ Cron job configured: $CRON_EXPR"

# Step 7: Test the setup
echo "🧪 Testing setup..."

# Check if main script exists and is executable
if [ -f "$SERVICE_DIR/scrobble_oracle.py" ]; then
    echo "   ✅ Main script found: scrobble_oracle.py"
else
    echo "   ❌ Main script not found: scrobble_oracle.py"
    exit 1
fi

# Check if virtual environment is working
if sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/python3" -c "import sys; print('Python version:', sys.version)" >/dev/null 2>&1; then
    echo "   ✅ Virtual environment is working"
else
    echo "   ❌ Virtual environment issue"
    exit 1
fi

# Check if required packages are installed
if sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/python3" -c "import ytmusicapi, pylast, fuzzywuzzy" >/dev/null 2>&1; then
    echo "   ✅ Required packages are installed"
else
    echo "   ❌ Missing required packages"
    echo "   Run: sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Verify cron job was added
if sudo -u "$SERVICE_USER" crontab -l 2>/dev/null | grep -q "scrobble_oracle.py"; then
    echo "   ✅ Cron job verified"
else
    echo "   ❌ Cron job not found"
    exit 1
fi

echo ""
echo "🎉 Redeployment completed successfully!"
echo ""
echo "📋 Summary:"
echo "   - Backup created: $BACKUP_DIR"
echo "   - Code updated from repository"
echo "   - Dependencies updated"
echo "   - Configuration and history preserved"
echo "   - Cron job: every $CRON_INTERVAL minutes ($CRON_EXPR)"
echo ""
echo "🔧 Management commands:"
echo "   View logs:        sudo -u $SERVICE_USER tail -f $SERVICE_DIR/config/scrobble.log"
echo "   View cron jobs:   sudo -u $SERVICE_USER crontab -l"
echo "   Manual run:       sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py"
echo "   View history:     sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/history_manager.py stats"
echo ""
echo "⚠️  If you need to rollback, restore from: $BACKUP_DIR"
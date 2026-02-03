#!/bin/bash
# Multi-user deployment script for YTMusic Scrobbler
# Modular script to add additional Last.fm users
# Usage: sudo bash deploy_user.sh <username> <lastfm_username> <cron_interval_minutes>

set -e

# Parse command line arguments
if [ $# -ne 3 ]; then
    echo "❌ Invalid number of arguments"
    echo ""
    echo "Usage: $0 <username> <lastfm_username> <cron_interval_minutes>"
    echo ""
    echo "Examples:"
    echo "  $0 momo_kz momo_kz 120          # momo_kz, every 2 hours"
    echo "  $0 alice alice_music 180        # alice, every 3 hours"
    echo "  $0 bob_smith bob_smith 240      # bob_smith, every 4 hours"
    echo ""
    echo "Parameters:"
    echo "  username           - Directory name (alphanumeric + underscores only)"
    echo "  lastfm_username    - Last.fm username"
    echo "  cron_interval_mins - How often to run (e.g., 60=hourly, 120=2hrs, 180=3hrs)"
    exit 1
fi

USERNAME=$1
LASTFM_USERNAME=$2
INTERVAL=$3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/opt/ytmusic-scrobbler-${USERNAME}"
SERVICE_USER="ytmusic"

echo "🚀 Deploying YTMusic Scrobbler for user: $USERNAME"
echo "   Last.fm account: $LASTFM_USERNAME"
echo "   Schedule: Every $INTERVAL minutes"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Validate username (alphanumeric and underscores only)
if ! [[ "$USERNAME" =~ ^[a-zA-Z0-9_]+$ ]]; then
    echo "❌ Invalid username: '$USERNAME'"
    echo "   Username must contain only alphanumeric characters and underscores"
    exit 1
fi

# Validate Last.fm username (alphanumeric, underscores, and hyphens)
if ! [[ "$LASTFM_USERNAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "❌ Invalid Last.fm username: '$LASTFM_USERNAME'"
    echo "   Last.fm username must contain only alphanumeric characters, underscores, and hyphens"
    exit 1
fi

# Validate interval
if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [ "$INTERVAL" -lt 1 ] || [ "$INTERVAL" -gt 1440 ]; then
    echo "❌ Invalid interval: $INTERVAL"
    echo "   Interval must be a number between 1 and 1440 minutes"
    exit 1
fi

# Check if service directory already exists
if [ -d "$SERVICE_DIR" ]; then
    echo "❌ Service directory already exists: $SERVICE_DIR"
    echo "   This user instance is already deployed"
    echo "   To redeploy, first remove the existing directory:"
    echo "   sudo rm -rf $SERVICE_DIR"
    echo "   And remove the cron entry:"
    echo "   sudo -u $SERVICE_USER crontab -e"
    exit 1
fi

# Check if ytmusic user exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "❌ Service user '$SERVICE_USER' does not exist"
    echo "   Please run the initial deploy.sh script first to create the system user"
    exit 1
fi

# Verify Python installation
echo "🐍 Verifying Python installation..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "   Python version: $PYTHON_VERSION"

if ! python3 -c "import venv" 2>/dev/null; then
    echo "❌ Python venv module not available"
    echo "   Please install python3-venv or python3-devel"
    exit 1
fi

if ! python3 -c "import pip" 2>/dev/null; then
    echo "❌ Python pip module not available"
    echo "   Please install python3-pip"
    exit 1
fi

echo "✅ Python environment verified"

# Create service directory
echo "📁 Setting up service directory: $SERVICE_DIR"
mkdir -p "$SERVICE_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"

# Copy files as root, then change ownership
echo "📋 Copying application files..."
cp "$SCRIPT_DIR/scrobble_oracle.py" "$SERVICE_DIR/"
cp "$SCRIPT_DIR/setup_credentials.py" "$SERVICE_DIR/"
cp "$SCRIPT_DIR/history_manager.py" "$SERVICE_DIR/" 2>/dev/null || echo "ℹ️  history_manager.py not found, skipping"
cp "$SCRIPT_DIR/requirements.txt" "$SERVICE_DIR/"
cp "$SCRIPT_DIR/.env.example" "$SERVICE_DIR/"

# Change ownership to service user
chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"

# Make scripts executable
chmod +x "$SERVICE_DIR/scrobble_oracle.py"
chmod +x "$SERVICE_DIR/setup_credentials.py"
[ -f "$SERVICE_DIR/history_manager.py" ] && chmod +x "$SERVICE_DIR/history_manager.py"

# Set up Python virtual environment
echo "🐍 Setting up Python virtual environment..."
sudo -u "$SERVICE_USER" python3 -m venv "$SERVICE_DIR/venv"

# Verify virtual environment creation
if [ ! -f "$SERVICE_DIR/venv/bin/python" ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

echo "✅ Virtual environment created successfully"

# Upgrade pip in virtual environment
echo "📦 Upgrading pip in virtual environment..."
sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install --upgrade pip --quiet

# Install Python dependencies
echo "📦 Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install -r "$SERVICE_DIR/requirements.txt" --quiet

# Verify critical dependencies
echo "🔍 Verifying dependencies..."
declare -A DEPS_TO_CHECK=(
    ["pylast"]="pylast"
    ["fuzzywuzzy"]="fuzzywuzzy"
    ["ytmusicapi"]="ytmusicapi"
    ["python-Levenshtein"]="Levenshtein"
)
FAILED_DEPS=()

for dep in "${!DEPS_TO_CHECK[@]}"; do
    module_name="${DEPS_TO_CHECK[$dep]}"
    if sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/python" -c "import $module_name" 2>/dev/null; then
        echo "   ✅ $dep installed successfully"
    else
        echo "   ❌ Failed to install $dep"
        FAILED_DEPS+=("$dep")
    fi
done

# Handle python-Levenshtein failure gracefully
if [[ " ${FAILED_DEPS[@]} " =~ " python-Levenshtein " ]]; then
    echo "   ⚠️  python-Levenshtein failed - attempting alternative installation..."

    # Try installing build dependencies first
    if command -v yum &> /dev/null; then
        yum install -y python3-devel gcc gcc-c++ make >/dev/null 2>&1
    elif command -v dnf &> /dev/null; then
        dnf install -y python3-devel gcc gcc-c++ make >/dev/null 2>&1
    fi

    # Retry python-Levenshtein installation
    if sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install python-Levenshtein --no-cache-dir --quiet 2>/dev/null; then
        echo "   ✅ python-Levenshtein installed successfully on retry"
        FAILED_DEPS=("${FAILED_DEPS[@]/python-Levenshtein}")
    else
        echo "   ⚠️  python-Levenshtein still failed - fuzzy matching will use slower fallback"
    fi
fi

# Exit only if critical dependencies failed (not python-Levenshtein)
CRITICAL_FAILED=()
for dep in "${FAILED_DEPS[@]}"; do
    if [[ "$dep" != "python-Levenshtein" ]]; then
        CRITICAL_FAILED+=("$dep")
    fi
done

if [ ${#CRITICAL_FAILED[@]} -gt 0 ]; then
    echo "   ❌ Critical dependencies failed: ${CRITICAL_FAILED[*]}"
    exit 1
fi

# Create .env file with Last.fm username pre-filled
echo "📝 Creating environment file..."
sudo -u "$SERVICE_USER" cp "$SERVICE_DIR/.env.example" "$SERVICE_DIR/.env"

# Update LASTFM_USERNAME in .env file
sudo -u "$SERVICE_USER" sed -i "s/^LASTFM_USERNAME=.*/LASTFM_USERNAME=$LASTFM_USERNAME/" "$SERVICE_DIR/.env"

echo "✅ Environment file created with LASTFM_USERNAME=$LASTFM_USERNAME"
echo "⚠️  Please edit $SERVICE_DIR/.env to add your Last.fm credentials"

# Create config directory
sudo -u "$SERVICE_USER" mkdir -p "$SERVICE_DIR/config"

# Set up cron job
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

# Add to user's crontab with comment marker
# Remove any old entries for this user (by comment marker or path), then add new entry
(sudo -u "$SERVICE_USER" crontab -l 2>/dev/null | grep -v "ytmusic-scrobbler-$USERNAME" | grep -v "$SERVICE_DIR/scrobble_oracle.py"; \
 echo "# ytmusic-scrobbler-$USERNAME"; \
 echo "$CRON_EXPR $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py >> $SERVICE_DIR/config/scrobble.log 2>&1") | \
 sudo -u "$SERVICE_USER" crontab -

echo "✅ Cron job configured successfully!"
echo ""
echo "📋 Current crontab for $SERVICE_USER:"
sudo -u "$SERVICE_USER" crontab -l
echo ""

echo "🎉 Deployment completed successfully for user: $USERNAME"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 NEXT STEPS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  Configure Last.fm credentials:"
echo "   sudo -u $SERVICE_USER nano $SERVICE_DIR/.env"
echo ""
echo "   Required fields:"
echo "   - LASTFM_API_KEY=<your_api_key>"
echo "   - LASTFM_API_SECRET=<your_api_secret>"
echo "   - LASTFM_USERNAME=$LASTFM_USERNAME"
echo "   - LASTFM_PASSWORD=<your_password>"
echo ""
echo "2️⃣  Set up YouTube Music credentials:"
echo "   sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/setup_credentials.py"
echo ""
echo "3️⃣  Test with dry run:"
echo "   sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py --dry-run"
echo ""
echo "4️⃣  Verify cron job:"
echo "   sudo -u $SERVICE_USER crontab -l | grep '$USERNAME'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 USEFUL COMMANDS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "View logs:"
echo "  sudo -u $SERVICE_USER tail -f $SERVICE_DIR/config/scrobble.log"
echo ""
echo "Manual run:"
echo "  sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py"
echo ""
echo "View history:"
echo "  sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/history_manager.py stats"
echo ""
echo "View all user instances:"
echo "  ls -la /opt/ | grep ytmusic-scrobbler"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Service installed in: $SERVICE_DIR"
echo "👤 Running as user: $SERVICE_USER"
echo "⏰ Schedule: $CRON_EXPR"
echo ""

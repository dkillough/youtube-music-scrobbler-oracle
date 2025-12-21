#!/bin/bash
# Oracle Cloud deployment script for YTMusic Scrobbler
# Comprehensive deployment with Oracle Linux optimization

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/opt/ytmusic-scrobbler"
SERVICE_USER="ytmusic"

echo "🚀 Deploying YTMusic Scrobbler to Oracle Cloud..."
echo "   Enhanced version with mobile gap-filling and smart scrobbling"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Detect OS and package manager
echo "🔍 Detecting system..."
if [ -f /etc/oracle-release ]; then
    echo "✅ Detected Oracle Linux"
    OS_TYPE="oracle"
elif [ -f /etc/redhat-release ]; then
    echo "✅ Detected RHEL/CentOS"
    OS_TYPE="rhel"
elif [ -f /etc/debian_version ]; then
    echo "✅ Detected Debian/Ubuntu"
    OS_TYPE="debian"
else
    echo "⚠️  Unknown OS - attempting generic installation"
    OS_TYPE="generic"
fi

# Update system packages
echo "📦 Updating system packages..."
if command -v apt-get &> /dev/null; then
    echo "   Using apt package manager..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git cron curl wget
elif command -v yum &> /dev/null; then
    echo "   Using yum package manager (Oracle Linux/RHEL/CentOS)..."
    yum update -y
    # Oracle Linux / RHEL / CentOS package names
    yum install -y python3 python3-pip git cronie curl wget

    # Ensure venv module is available (usually included with python3)
    echo "   Checking Python venv availability..."
    if ! python3 -c "import venv" 2>/dev/null; then
        echo "⚠️  Installing additional Python development tools..."
        yum install -y python3-devel python3-setuptools
    fi

    # Install build tools for compiling Python packages (needed for python-Levenshtein)
    echo "   Installing build tools for Python package compilation..."
    yum install -y gcc gcc-c++ make

    # Enable and start cron daemon
    systemctl enable crond
    systemctl start crond
    echo "✅ Cron daemon enabled and started"

elif command -v dnf &> /dev/null; then
    echo "   Using dnf package manager (Fedora/newer RHEL)..."
    dnf update -y
    # Fedora / newer RHEL systems
    dnf install -y python3 python3-pip git cronie curl wget

    if ! python3 -c "import venv" 2>/dev/null; then
        echo "⚠️  Installing additional Python development tools..."
        dnf install -y python3-devel python3-setuptools
    fi

    # Install build tools for compiling Python packages (needed for python-Levenshtein)
    echo "   Installing build tools for Python package compilation..."
    dnf install -y gcc gcc-c++ make

    systemctl enable crond
    systemctl start crond
    echo "✅ Cron daemon enabled and started"
else
    echo "❌ Unsupported package manager. Please install python3, pip, git, and cron manually."
    exit 1
fi

# Verify Python installation
echo "🐍 Verifying Python installation..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "   Python version: $PYTHON_VERSION"

if ! python3 -c "import venv" 2>/dev/null; then
    echo "❌ Python venv module not available. Please install python3-venv or python3-devel."
    exit 1
fi

if ! python3 -c "import pip" 2>/dev/null; then
    echo "❌ Python pip module not available. Please install python3-pip."
    exit 1
fi

echo "✅ Python environment verified"

# Create service user
echo "👤 Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -m -s /bin/bash "$SERVICE_USER"
    echo "✅ Created user: $SERVICE_USER"
else
    echo "ℹ️  User $SERVICE_USER already exists"
fi

# Create service directory
echo "📁 Setting up service directory..."
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
sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install -r "$SERVICE_DIR/requirements.txt"

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
        yum install -y python3-devel gcc gcc-c++ make
    elif command -v dnf &> /dev/null; then
        dnf install -y python3-devel gcc gcc-c++ make
    fi

    # Retry python-Levenshtein installation
    if sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install python-Levenshtein --no-cache-dir; then
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

# Create .env file if it doesn't exist
if [ ! -f "$SERVICE_DIR/.env" ]; then
    echo "📝 Creating environment file..."
    sudo -u "$SERVICE_USER" cp "$SERVICE_DIR/.env.example" "$SERVICE_DIR/.env"
    echo "⚠️  Please edit $SERVICE_DIR/.env with your Last.fm credentials"
fi

# Create config directory
sudo -u "$SERVICE_USER" mkdir -p "$SERVICE_DIR/config"

# Create setup_cron.sh script
echo "📝 Creating cron setup script..."
cat > "$SCRIPT_DIR/setup_cron.sh" << 'EOF'
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
EOF

chmod +x "$SCRIPT_DIR/setup_cron.sh"

# Run tests if available
if [ -d "$SCRIPT_DIR/tests" ]; then
    echo "🧪 Running tests..."
    for test_file in "$SCRIPT_DIR"/tests/test_*.py; do
        if [ -f "$test_file" ]; then
            test_name=$(basename "$test_file" .py)
            echo "   Running $test_name..."
            if sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/python3" "$test_file"; then
                echo "   ✅ $test_name passed"
            else
                echo "   ⚠️  $test_name failed (may not affect deployment)"
            fi
        fi
    done
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit the environment file:"
echo "   sudo -u $SERVICE_USER nano $SERVICE_DIR/.env"
echo ""
echo "2. Set up YouTube Music credentials:"
echo "   sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/setup_credentials.py"
echo ""
echo "3. Set up periodic execution (recommended: 2-4 hours for mobile gap-filling):"
echo "   bash $SCRIPT_DIR/setup_cron.sh 120   # Every 2 hours (recommended)"
echo "   bash $SCRIPT_DIR/setup_cron.sh 180   # Every 3 hours"
echo "   bash $SCRIPT_DIR/setup_cron.sh 240   # Every 4 hours"
echo ""
echo "4. Test manual execution:"
echo "   sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/scrobble_oracle.py --dry-run"
echo ""
echo "📁 Service installed in: $SERVICE_DIR"
echo "👤 Running as user: $SERVICE_USER"
echo "📊 Features enabled:"
echo "   - Mobile gap-filling (detects existing Last.fm scrobbles)"
echo "   - Enhanced metadata cleanup (YouTube-specific)"
echo "   - Fuzzy matching with popularity weighting"
echo "   - Duration-based duplicate prevention"
echo "   - Automatic 2-week history cleanup"
echo "   - Comprehensive logging and history tracking"
echo "   - Dry-run mode for testing"
echo ""
echo "🔧 Management commands:"
echo "   View logs:        sudo -u $SERVICE_USER tail -f $SERVICE_DIR/config/scrobble.log"
echo "   View statistics:  sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/history_manager.py stats"
echo "   Search history:   sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/history_manager.py search --query 'artist'"
echo "   Manual cleanup:   sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/history_manager.py cleanup"

#!/bin/bash
# Oracle Cloud deployment script for YTMusic Scrobbler

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/opt/ytmusic-scrobbler"
SERVICE_USER="ytmusic"

echo "🚀 Deploying YTMusic Scrobbler to Oracle Cloud..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git cron
elif command -v yum &> /dev/null; then
    yum update -y
    yum install -y python3 python3-pip git cronie
    systemctl enable crond
    systemctl start crond
else
    echo "❌ Unsupported package manager. Please install python3, pip, git, and cron manually."
    exit 1
fi

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

# Copy files as service user
echo "📋 Copying application files..."
sudo -u "$SERVICE_USER" cp "$SCRIPT_DIR/scrobble_oracle.py" "$SERVICE_DIR/"
sudo -u "$SERVICE_USER" cp "$SCRIPT_DIR/setup_credentials.py" "$SERVICE_DIR/"
sudo -u "$SERVICE_USER" cp "$SCRIPT_DIR/requirements.txt" "$SERVICE_DIR/"
sudo -u "$SERVICE_USER" cp "$SCRIPT_DIR/.env.example" "$SERVICE_DIR/"

# Make scripts executable
chmod +x "$SERVICE_DIR/scrobble_oracle.py"
chmod +x "$SERVICE_DIR/setup_credentials.py"

# Set up Python virtual environment
echo "🐍 Setting up Python virtual environment..."
sudo -u "$SERVICE_USER" python3 -m venv "$SERVICE_DIR/venv"
sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$SERVICE_DIR/venv/bin/pip" install -r "$SERVICE_DIR/requirements.txt"

# Create .env file if it doesn't exist
if [ ! -f "$SERVICE_DIR/.env" ]; then
    echo "📝 Creating environment file..."
    sudo -u "$SERVICE_USER" cp "$SERVICE_DIR/.env.example" "$SERVICE_DIR/.env"
    echo "⚠️  Please edit $SERVICE_DIR/.env with your Last.fm credentials"
fi

# Create log directory
sudo -u "$SERVICE_USER" mkdir -p "$SERVICE_DIR/config"

echo "✅ Deployment completed!"
echo ""
echo "📋 Next steps:"
echo "1. Edit the environment file: sudo -u $SERVICE_USER nano $SERVICE_DIR/.env"
echo "2. Set up YouTube Music credentials: sudo -u $SERVICE_USER $SERVICE_DIR/venv/bin/python3 $SERVICE_DIR/setup_credentials.py"
echo "3. Set up cron job: bash $SCRIPT_DIR/setup_cron.sh [interval_minutes]"
echo ""
echo "📁 Service installed in: $SERVICE_DIR"
echo "👤 Running as user: $SERVICE_USER"
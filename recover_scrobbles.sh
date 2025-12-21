#!/bin/bash
#
# YouTube Music Scrobble Recovery Script
# Recovers missed scrobbles from a specified time window
#
# Usage: ./recover_scrobbles.sh <hours> [--dry-run]
#   <hours>    - Number of hours to look back (e.g., 48 for last 2 days)
#   --dry-run  - Preview what would be scrobbled without actually doing it
#
# Example: ./recover_scrobbles.sh 48 --dry-run
#

set -e  # Exit on error

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Parse arguments
if [ $# -lt 1 ]; then
    print_error "Usage: $0 <hours> [--dry-run]"
    echo ""
    echo "Examples:"
    echo "  $0 48          # Recover last 48 hours"
    echo "  $0 48 --dry-run  # Preview what would be recovered"
    echo ""
    exit 1
fi

HOURS=$1
DRY_RUN=""

if [ $# -gt 1 ] && [ "$2" = "--dry-run" ]; then
    DRY_RUN="--dry-run"
    print_warning "DRY RUN MODE - No actual scrobbling will occur"
fi

# Validate hours is a number
if ! [[ "$HOURS" =~ ^[0-9]+$ ]]; then
    print_error "Hours must be a positive number"
    exit 1
fi

# Validate hours is reasonable (not more than 168 hours = 1 week)
if [ "$HOURS" -gt 168 ]; then
    print_warning "Warning: Requesting $HOURS hours (more than 1 week)"
    print_warning "YouTube Music history may not go back that far"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Recovery cancelled"
        exit 0
    fi
fi

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    print_error "Configuration file .env not found"
    print_error "Please ensure .env exists with Last.fm credentials"
    exit 1
fi

# Check if browser.json exists
if [ ! -f "$SCRIPT_DIR/config/browser.json" ]; then
    print_error "YouTube Music credentials not found (config/browser.json)"
    print_error "Please run setup first to authenticate with YouTube Music"
    exit 1
fi

# Check if Python venv exists (for Oracle setup)
PYTHON_CMD="python3"
if [ -d "/opt/ytmusic-scrobbler/venv" ]; then
    PYTHON_CMD="/opt/ytmusic-scrobbler/venv/bin/python3"
    print_info "Using virtual environment Python"
fi

# Calculate max scrobbles for recovery (higher than normal runs)
# Estimate: assume average 3-minute songs, calculate how many tracks could fit
ESTIMATED_MAX_TRACKS=$((HOURS * 20))  # ~20 tracks per hour
if [ "$ESTIMATED_MAX_TRACKS" -lt 50 ]; then
    ESTIMATED_MAX_TRACKS=50
fi
if [ "$ESTIMATED_MAX_TRACKS" -gt 200 ]; then
    ESTIMATED_MAX_TRACKS=200
fi

print_info "Recovery Configuration:"
echo "  Time window: Last $HOURS hours"
echo "  Max scrobbles: $ESTIMATED_MAX_TRACKS tracks"
[ -n "$DRY_RUN" ] && echo "  Mode: DRY RUN (preview only)"
echo ""

# Prepare recovery command with environment overrides
print_info "Starting recovery process..."
echo ""

# Export environment variables for the recovery run
export RECENT_WINDOW_HOURS="$HOURS"
export MAX_SCROBBLES_PER_RUN="$ESTIMATED_MAX_TRACKS"
export ENABLE_MOBILE_DETECTION="true"  # Always enable to avoid duplicating mobile scrobbles

# Run the scrobbler with recovery parameters
if [ -n "$DRY_RUN" ]; then
    sudo -u ytmusic env \
        RECENT_WINDOW_HOURS="$HOURS" \
        MAX_SCROBBLES_PER_RUN="$ESTIMATED_MAX_TRACKS" \
        ENABLE_MOBILE_DETECTION="true" \
        "$PYTHON_CMD" "$SCRIPT_DIR/scrobble_oracle.py" --dry-run
else
    sudo -u ytmusic env \
        RECENT_WINDOW_HOURS="$HOURS" \
        MAX_SCROBBLES_PER_RUN="$ESTIMATED_MAX_TRACKS" \
        ENABLE_MOBILE_DETECTION="true" \
        "$PYTHON_CMD" "$SCRIPT_DIR/scrobble_oracle.py"
fi

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    if [ -n "$DRY_RUN" ]; then
        print_success "Dry run completed successfully"
        print_info "Run without --dry-run to actually scrobble these tracks"
    else
        print_success "Recovery completed successfully!"
        print_info "Check config/scrobble.log for detailed results"
    fi
else
    print_error "Recovery failed with exit code $RESULT"
    print_info "Check config/scrobble.log for error details"
    exit $RESULT
fi

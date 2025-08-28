# YTMusic Scrobbler - Oracle Cloud Edition

This is a converted version of the YTMusic Scrobbler that runs as a periodic script on Oracle Cloud OCI compute instances instead of a continuous Docker container.

## Features

- 🎵 Scrobbles YouTube Music listening history to Last.fm
- 🔄 Runs periodically via cron (configurable interval)
- 📊 Comprehensive logging and history tracking
- 🛡️ Error handling and credential management
- 🏗️ Easy deployment on Oracle Cloud
- 🗂️ Duplicate prevention with 2-week lookback
- 📈 History management utilities
- ⏰ Intelligent timestamp handling for batch scrobbles
- 🔍 Fuzzy matching for accurate Last.fm track matching
- 📈 Popularity-based track selection (prefers tracks with more listeners)

## Prerequisites

- Oracle Cloud OCI compute instance (Ubuntu/CentOS recommended)
- Python 3.6+ installed
- Last.fm API credentials ([Get them here](https://www.last.fm/api/account/create))
- YouTube Music account with listening history

## Quick Start

### 1. Deploy to Oracle Cloud

```bash
# Clone the repository (or upload the oracle directory)
git clone <your-repo-url>
cd ytmusicscrobbler/oracle

# Run deployment script (as root)
sudo bash deploy.sh
```

### 2. Configure Last.fm Credentials

```bash
# Edit the environment file
sudo -u ytmusic nano /opt/ytmusic-scrobbler/.env
```

Add your Last.fm credentials:
```env
LASTFM_API_KEY=your_api_key_here
LASTFM_API_SECRET=your_api_secret_here
LASTFM_USERNAME=your_username
LASTFM_PASSWORD=your_password
```

### 3. Set Up YouTube Music Credentials

```bash
# Run the interactive setup
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/setup_credentials.py
```

Follow the instructions to copy your browser headers from YouTube Music.

### 4. Set Up Periodic Execution

```bash
# Set up cron job to run every 5 minutes
sudo bash setup_cron.sh 5

# Or choose a different interval (in minutes)
sudo bash setup_cron.sh 10  # Every 10 minutes
sudo bash setup_cron.sh 60  # Every hour
```

## File Structure

```
/opt/ytmusic-scrobbler/
├── scrobble_oracle.py     # Main scrobbling script
├── setup_credentials.py   # YouTube Music credential setup
├── history_manager.py     # History management utility
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── venv/                  # Python virtual environment
└── config/
    ├── browser.json           # YouTube Music credentials (auto-generated)
    ├── history.txt            # Legacy last scrobbled track ID
    ├── scrobble_history.json  # Comprehensive scrobble history (JSON)
    └── scrobble.log           # Application logs
```

## History Management

The enhanced version maintains comprehensive scrobble history to prevent duplicates and provides lookback functionality.

### History Manager Utility

```bash
# View scrobble statistics
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py stats

# List recent scrobbles (default: 7 days)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py list

# List scrobbles from last 14 days
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py list --days 14

# Search for specific tracks
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py search --query "artist name"

# Manual cleanup (dry run - see what would be removed)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py cleanup

# Manual cleanup (actually remove old entries)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py cleanup --force

# Automatic cleanup with storage info (used internally)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py auto-cleanup
```

## Monitoring

### View Logs
```bash
# Real-time logs
sudo -u ytmusic tail -f /opt/ytmusic-scrobbler/config/scrobble.log

# Recent log entries
sudo -u ytmusic tail -20 /opt/ytmusic-scrobbler/config/scrobble.log
```

### Check Cron Jobs
```bash
# View current cron schedule
sudo -u ytmusic crontab -l

# Edit cron jobs
sudo -u ytmusic crontab -e
```

### Manual Test Run
```bash
# Test the script manually
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py
```

## Troubleshooting

### YouTube Music Credentials Expired
If you see errors about invalid credentials:
```bash
# Re-run the credential setup
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/setup_credentials.py
```

### Last.fm Connection Issues
- Verify your API credentials in `/opt/ytmusic-scrobbler/.env`
- Check that your Last.fm account is active

### No New Scrobbles
- The script only scrobbles new tracks since the last run
- Check that you have recent listening history on YouTube Music
- Verify the script is running: `sudo -u ytmusic crontab -l`

## How It Works

### Smart Duplicate Prevention with Automatic Cleanup
- Maintains a comprehensive JSON history file (`scrobble_history.json`)
- Tracks all scrobbled tracks with timestamps, duration, and metadata
- Allows same track multiple times per day if sufficient time gap exists
- **Time gap requirement**: Track duration + 30 seconds buffer
- **Perfect for repeated listening**: Supports tracks on loop/repeat
- **🗑️ Automatic cleanup**: Removes entries older than 2 weeks on every run
- **💾 Storage leak prevention**: Prevents unlimited history file growth
- **⚡ Efficient**: Only saves when cleanup actually removes entries
- Prevents duplicate scrobbles even across service restarts

### Two-Week Lookback with Smart Timing
- Scans all tracks in YouTube Music history from past 2 weeks
- **Duration-aware duplicate checking**: Each track can be scrobbled multiple times if:
  - Time gap > track duration + 30 seconds
  - Supports natural listening patterns (replaying favorites, loop mode)
- Batch scrobbles valid tracks with appropriate timestamps
- Maintains chronological order for better Last.fm history
- Handles rate limiting between scrobbles (2-minute spacing)

### Smart Timestamps & Duration Tracking
- Extracts track duration from YouTube Music API
- Recent tracks get current timestamps
- Batch scrobbles use spaced timestamps (2 minutes apart)
- **Intelligent gap calculation**: Prevents scrobbling same track within (duration + 30s)
- Preserves listening order in Last.fm history
- Supports realistic listening patterns (allowing repeats after full plays)

### Enhanced Metadata Cleanup & Fuzzy Matching
- **YouTube-specific cleanup**: Removes "- Topic", "VEVO", "(Official Video)", etc.
- **Featuring normalization**: Handles "feat.", "featuring", "ft", "x", "with" variations
- **Remix/version standardization**: Cleans "(Original Mix)", standardizes "(Radio Edit)"
- **Symbol normalization**: Converts "&" to "and", cleans excessive punctuation
- **Fuzzy string matching**: Finds best Last.fm track matches after cleanup
- **Popularity-based selection**: Weighted scoring (70% similarity + 30% listener count)
- **Smart fallback**: Uses cleaned metadata if no good matches found (>60% similarity)
- **Comprehensive logging**: Shows original → cleaned → matched transformations

## Differences from Docker Version

| Feature | Docker Version | Oracle Cloud Version |
|---------|---------------|---------------------|
| Execution | Continuous loop | Periodic cron job |
| Web UI | Flask server for setup | Interactive CLI setup |
| Configuration | Volume mounts | Local file system |
| Monitoring | Container logs | System logs + files |
| Resource Usage | Always running | Only runs when needed |
| History Tracking | Simple last track ID | Comprehensive JSON history |
| Duplicate Prevention | Basic | Smart duration-based with 2-week lookback |
| Batch Processing | Single track per run | Multiple tracks per run with gap validation |
| Track Matching | Exact match only | Fuzzy matching with popularity weighting |
| Repeat Handling | Blocks all duplicates | Allows repeats after track duration + buffer |

## Security Notes

- The service runs as a dedicated `ytmusic` user with limited privileges
- Credentials are stored in the service user's directory
- Log files are accessible only to the service user and root

## Uninstall

To completely remove the service:

```bash
# Remove cron job
sudo -u ytmusic crontab -r

# Remove service directory
sudo rm -rf /opt/ytmusic-scrobbler

# Remove service user (optional)
sudo userdel -r ytmusic
```
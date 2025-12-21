# YTMusic Scrobbler - Oracle Cloud Edition

This is a converted version of the YTMusic Scrobbler that runs as a periodic script on Oracle Cloud OCI compute instances instead of a continuous Docker container.

## Features

- 🎵 Scrobbles YouTube Music listening history to Last.fm
- 📱 **Mobile Gap-Filling**: Automatically detects and skips tracks already scrobbled from mobile extensions
- 🔄 Runs periodically via cron (recommended: every 2-3 hours)
- 📊 Comprehensive logging and history tracking
- 🛡️ Error handling and credential management
- 🏗️ Easy deployment on Oracle Cloud (Oracle Linux optimized)
- 🗂️ Smart duplicate prevention with duration-based gaps
- 📈 History management utilities
- ⏰ Intelligent timestamp estimation for "Today" tracks
- 🔍 Fuzzy matching for accurate Last.fm track matching
- 📈 Popularity-based track selection (prefers tracks with more listeners)
- 🧪 Dry-run mode for testing without actual scrobbling
- 🔁 Automatic 2-week history cleanup to prevent storage bloat

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

Add your Last.fm credentials and configure mobile gap-filling:
```env
# Last.fm API Credentials
LASTFM_API_KEY=your_api_key_here
LASTFM_API_SECRET=your_api_secret_here
LASTFM_USERNAME=your_username
LASTFM_PASSWORD=your_password

# Mobile Gap-Filling Configuration (optional - defaults shown)
RECENT_WINDOW_HOURS=2          # Check Last.fm for scrobbles from last N hours
MAX_SCROBBLES_PER_RUN=20       # Rate limit protection
ENABLE_MOBILE_DETECTION=true   # Skip tracks already on Last.fm
DRY_RUN=false                  # Set true for testing
```

### 3. Set Up YouTube Music Credentials

```bash
# Run the interactive setup
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/setup_credentials.py
```

Follow the instructions to copy your browser headers from YouTube Music.

### 4. Test with Dry Run

```bash
# Test what would be scrobbled without actually scrobbling
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run
```

### 5. Set Up Periodic Execution

```bash
# Recommended: Run every 2-3 hours for mobile gap-filling
sudo bash setup_cron.sh 120  # Every 2 hours (recommended)
sudo bash setup_cron.sh 180  # Every 3 hours
sudo bash setup_cron.sh 240  # Every 4 hours
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
# Test with dry run (see what would be scrobbled without actually scrobbling)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run

# Run the script manually (actually scrobble)
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

### Mobile Gap-Filling (New!)
- **Cross-references Last.fm**: Fetches your recent scrobbles (last 2 hours by default)
- **Smart detection**: Automatically skips tracks already scrobbled from mobile extensions
- **Fills the gaps**: Only scrobbles tracks missing from Last.fm (mobile-only listening)
- **Configurable window**: Adjust `RECENT_WINDOW_HOURS` for your needs
- **Rate-limit safe**: Max 21 API calls per run (1 getRecentTracks + up to 20 scrobbles)

### YouTube Music "Today" Processing
- **Limitation**: YouTube Music API only provides relative dates ("Today", "Yesterday")
- **Focus on Today**: Only processes tracks from "Today" section for accuracy
- **Timestamp estimation**: Works backwards from current time using track durations
- **Realistic spacing**: Each track gets duration + 30s buffer spacing
- **24-hour limit**: Won't go back more than 24 hours to maintain accuracy

### Smart Duplicate Prevention with Automatic Cleanup
- Maintains a comprehensive JSON history file (`scrobble_history.json`)
- Tracks all scrobbled tracks with timestamps, duration, source, and metadata
- **Source tracking**: Distinguishes between bot scrobbles and detected mobile scrobbles
- **Time gap requirement**: Track duration + 30 seconds buffer
- **Perfect for repeated listening**: Supports tracks on loop/repeat
- **🗑️ Automatic cleanup**: Removes entries older than 2 weeks on every run
- **💾 Storage leak prevention**: Prevents unlimited history file growth
- Prevents duplicate scrobbles even across service restarts

### Smart Timestamps & Duration Tracking
- Extracts track duration from YouTube Music API
- Estimates timestamps based on track position in "Today" section
- Batch scrobbles use duration-aware spacing (not fixed intervals)
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
| Duplicate Prevention | Basic | Smart duration-based + mobile detection |
| Mobile Detection | None | Cross-references Last.fm to avoid duplicates |
| Batch Processing | Single track per run | Multiple "Today" tracks per run |
| Track Matching | Exact match only | Fuzzy matching with popularity weighting |
| Timestamp Handling | Basic | Intelligent estimation based on track order |
| Repeat Handling | Blocks all duplicates | Allows repeats after track duration + buffer |
| Dry Run Mode | None | Full dry-run support for testing |

## Known Limitations

### YouTube Music API Constraints
- **No exact timestamps**: YouTube Music only provides relative dates ("Today", "Yesterday")
- **Today only**: Bot only processes tracks from "Today" section for accuracy
- **Estimation required**: Timestamps are estimated based on track order and durations
- **24-hour window**: Won't process tracks older than 24 hours

### Mobile Detection
- **Recent window only**: Only checks Last.fm for scrobbles from last N hours (default: 2)
- **Not perfect**: If mobile extension delays scrobbling, bot may create duplicate
- **Solution**: Run bot every 2-3 hours to minimize overlap
- **Can be disabled**: Set `ENABLE_MOBILE_DETECTION=false` if causing issues

### Loop Detection
- **Limited to Today**: Can only detect loops within "Today" section
- **Order-based**: Relies on track appearing multiple times in history
- **Best effort**: YouTube Music may not always show all loop iterations

### Rate Limiting
- **Max tracks per run**: Default 20 tracks to avoid rate limiting
- **2-second delays**: Between scrobbles to be respectful to Last.fm API
- **Periodic execution**: Running every 2-3 hours is safe and recommended

### General Notes
- Bot won't catch up on old history (>24 hours ago)
- First run may miss some tracks - this is expected
- Mobile extensions should remain your primary scrobbling method
- This bot is designed to **fill gaps**, not replace mobile scrobbling

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
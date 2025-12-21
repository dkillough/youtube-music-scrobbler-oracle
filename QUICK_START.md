# Quick Start Guide - YouTube Music Scrobbler

## TL;DR

```bash
# 1. Deploy (as root)
sudo bash deploy.sh

# 2. Configure Last.fm
sudo -u ytmusic nano /opt/ytmusic-scrobbler/.env

# 3. Set up YouTube Music credentials
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/setup_credentials.py

# 4. Test with dry run
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run

# 5. Set up cron (every 2 hours)
sudo bash setup_cron.sh 120
```

## Configuration Options

Edit `/opt/ytmusic-scrobbler/.env`:

```env
# Required
LASTFM_API_KEY=your_api_key_here
LASTFM_API_SECRET=your_api_secret_here
LASTFM_USERNAME=your_username
LASTFM_PASSWORD=your_password

# Optional (defaults shown)
RECENT_WINDOW_HOURS=2          # Check Last.fm for scrobbles from last N hours
MAX_SCROBBLES_PER_RUN=20       # Rate limit protection
ENABLE_MOBILE_DETECTION=true   # Skip tracks already on Last.fm
DRY_RUN=false                  # Preview mode
```

## Common Commands

### View Logs
```bash
# Real-time
sudo -u ytmusic tail -f /opt/ytmusic-scrobbler/config/scrobble.log

# Last 50 lines
sudo -u ytmusic tail -50 /opt/ytmusic-scrobbler/config/scrobble.log
```

### Manual Runs
```bash
# Dry run (see what would be scrobbled)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run

# Live run (actually scrobble)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py
```

### History Management
```bash
# View statistics
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py stats

# List recent scrobbles
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py list

# Search for artist/track
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py search --query "Artist Name"

# Clean old entries (dry run)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py cleanup

# Clean old entries (actually remove)
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/history_manager.py cleanup --force
```

### Cron Management
```bash
# View cron jobs
sudo -u ytmusic crontab -l

# Edit cron jobs
sudo -u ytmusic crontab -e

# Change interval (every 3 hours)
sudo bash setup_cron.sh 180
```

### Troubleshooting

#### YouTube Music credentials expired
```bash
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/setup_credentials.py
```

#### Check if service is working
```bash
# 1. Check cron is running
systemctl status crond

# 2. Check cron job exists
sudo -u ytmusic crontab -l | grep scrobble

# 3. Run manually with dry-run
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run

# 4. Check logs for errors
sudo -u ytmusic tail -50 /opt/ytmusic-scrobbler/config/scrobble.log
```

#### No tracks being scrobbled
Possible reasons:
1. **All tracks on Last.fm**: Mobile extension already scrobbled them
2. **No "Today" tracks**: YouTube Music history only shows older tracks
3. **Bot history full**: All tracks already processed by bot
4. **Mobile detection issue**: Try disabling with `ENABLE_MOBILE_DETECTION=false`

Check with dry run:
```bash
sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run
```

#### Duplicate scrobbles
If you're getting duplicates despite mobile detection:
1. **Increase recent window**: Set `RECENT_WINDOW_HOURS=4` or higher
2. **Run less frequently**: Use 3-4 hour intervals instead of 2
3. **Check mobile extension**: Ensure it's scrobbling immediately

## Understanding the Logs

### Good Run Example
```
INFO: Starting YouTube Music scrobbler with mobile gap-filling (LIVE MODE)...
INFO: Connected to Last.fm successfully
INFO: Fetching Last.fm scrobbles from last 2 hours...
INFO: Found 5 scrobbles on Last.fm in recent window (4 unique tracks)
INFO: Successfully logged into YouTube Music
INFO: Retrieved 12 tracks from history
INFO: Extracted 8 tracks from 'Today' section
INFO: Processing 8 tracks from 'Today' with mobile gap detection...
============================================================
INFO:   ✓ Track A - Artist A
INFO:     └─ Found on Last.fm (~5m difference), skipping (mobile scrobble)
INFO:   ✓ Track B - Artist B
INFO:     └─ Found on Last.fm (~12m difference), skipping (mobile scrobble)
INFO:   → Track C - Artist C
INFO:     └─ Will scrobble at 14:32:15 (estimated)
INFO:   → Track D - Artist D
INFO:     └─ Will scrobble at 15:05:30 (estimated)
============================================================
INFO: Result: 2 tracks ready to scrobble (out of 8 from today)
INFO: 📊 Summary: Will scrobble 2 tracks
INFO: Scrobbling (1/2): Artist C - Track C at 2025-10-20 14:32:15
INFO: Successfully scrobbled at 14:32:15
INFO: Scrobbling (2/2): Artist D - Track D at 2025-10-20 15:05:30
INFO: Successfully scrobbled at 15:05:30
INFO: ✅ Successfully scrobbled 2/2 tracks
```

### Key Log Indicators

- `✓` = Track skipped (found on Last.fm or in bot history)
- `→` = Track will be scrobbled
- `⏸️` = Processing stopped (hit limit or 24-hour boundary)
- `[DRY RUN]` = Dry run mode, not actually scrobbling

## Recommended Setup

### For Most Users
```bash
# Every 2 hours (good balance)
sudo bash setup_cron.sh 120
```

Configuration:
```env
RECENT_WINDOW_HOURS=2          # Check last 2 hours
ENABLE_MOBILE_DETECTION=true   # Skip mobile scrobbles
MAX_SCROBBLES_PER_RUN=20       # Rate limit protection
```

### For Heavy Listeners
```bash
# Every 1 hour
sudo bash setup_cron.sh 60
```

Configuration:
```env
RECENT_WINDOW_HOURS=4          # Wider window
ENABLE_MOBILE_DETECTION=true
MAX_SCROBBLES_PER_RUN=30       # More tracks per run
```

### For Light Listeners
```bash
# Every 4 hours
sudo bash setup_cron.sh 240
```

Configuration:
```env
RECENT_WINDOW_HOURS=2
ENABLE_MOBILE_DETECTION=true
MAX_SCROBBLES_PER_RUN=20
```

### Without Mobile Extension
If you don't use mobile scrobbling extensions:
```env
RECENT_WINDOW_HOURS=2
ENABLE_MOBILE_DETECTION=false   # Don't cross-reference
MAX_SCROBBLES_PER_RUN=50        # More tracks since no overlap
```

## What to Expect

### First Run
- Bot will process tracks from "Today" only
- May scrobble 5-20 tracks (depending on your listening)
- Check logs to see what was scrobbled

### Regular Runs
- Most runs will scrobble 0-5 tracks
- Tracks scrobbled by mobile will be skipped
- Only fills gaps in your Last.fm history

### What NOT to Expect
- ❌ Bot won't scrobble old history (yesterday or older)
- ❌ Won't detect loops perfectly (YouTube Music limitation)
- ❌ Timestamps are estimated, not exact
- ❌ Can't replace mobile extensions (designed to complement them)

## Files & Locations

```
/opt/ytmusic-scrobbler/           # Service directory
├── scrobble_oracle.py            # Main script
├── setup_credentials.py          # YouTube Music setup
├── history_manager.py            # History utilities
├── .env                          # Your configuration
├── venv/                         # Python virtual environment
└── config/
    ├── browser.json              # YouTube Music credentials
    ├── scrobble_history.json     # Bot history
    └── scrobble.log              # Logs
```

## Getting Help

1. **Check logs first**: `sudo -u ytmusic tail -50 /opt/ytmusic-scrobbler/config/scrobble.log`
2. **Try dry-run**: See what the bot would do
3. **Read limitations**: Check README for known issues
4. **GitHub issues**: Report bugs with log excerpts

## Updating

Use the redeploy script:
```bash
sudo bash redeploy.sh 120  # 120 = cron interval in minutes
```

This preserves your configuration and history.

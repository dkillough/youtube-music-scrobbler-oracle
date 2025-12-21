# Changelog

## Version 2.0.0 - Mobile Gap-Filling Release (2025-10-20)

### Major Features

#### 🆕 Mobile Gap-Filling
- **Cross-reference with Last.fm**: Bot now fetches recent scrobbles from Last.fm to detect what's already been scrobbled
- **Smart detection**: Automatically skips tracks that were already scrobbled by mobile extensions or other sources
- **Configurable window**: Check Last.fm for scrobbles from last N hours (default: 2 hours)
- **Rate-limit safe**: Minimal API calls (1 getRecentTracks + max 20 scrobbles per run)

#### 🎯 "Today" Focus Strategy
- **Limitation acknowledged**: YouTube Music API only provides relative dates, not exact timestamps
- **Accurate processing**: Only processes tracks from "Today" section to avoid timestamp estimation errors
- **Smart estimation**: Works backwards from current time using track durations
- **24-hour safety limit**: Won't attempt to estimate timestamps beyond 24 hours

#### 🧪 Dry-Run Mode
- **Test safely**: Run with `--dry-run` flag to see what would be scrobbled without actually scrobbling
- **Environment variable**: Can also set `DRY_RUN=true` in `.env`
- **Full logging**: Shows all decision logic in dry-run mode

### Improvements

#### Repository Cleanup
- **Consolidated deployment**: Merged `deploy.sh` and `oracle_deploy.sh` into single `deploy.sh`
- **Removed duplicate**: Deleted obsolete `oracle_deploy.sh`
- **Kept redeploy script**: `redeploy.sh` remains separate for updates

#### Enhanced Configuration
- **New `.env` options**:
  - `RECENT_WINDOW_HOURS`: How far back to check Last.fm (default: 2)
  - `MAX_SCROBBLES_PER_RUN`: Rate limit protection (default: 20)
  - `ENABLE_MOBILE_DETECTION`: Toggle mobile gap-filling (default: true)
  - `DRY_RUN`: Enable dry-run mode (default: false)

#### Updated History Schema
- **Source tracking**: Each scrobble now records its source (`ytmusic_bot` or `mobile_extension`)
- **Better debugging**: Can identify which scrobbles came from where
- **Backward compatible**: Existing history files work fine

#### Improved Logging
- **Detailed decisions**: Shows why each track was scrobbled or skipped
- **Mobile detection logs**: Clear indication when tracks found on Last.fm
- **Summary reports**: Before and after scrobbling summaries
- **Tree-style output**: Clean, hierarchical log format

#### Updated Cron Recommendations
- **Longer intervals**: Now recommends 2-4 hour intervals (not 5-10 minutes)
- **Rationale**: Works better with "Today" focus and mobile gap-filling
- **Rate-limit safe**: Less frequent runs = fewer API calls

### Technical Changes

#### New Functions
- `get_lastfm_recent_scrobbles()`: Fetches recent scrobbles from Last.fm
- `extract_today_tracks()`: Extracts only "Today" tracks from YouTube Music history
- `is_track_in_lastfm_recent()`: Checks if track exists in Last.fm recent window
- `process_today_tracks_with_gap_detection()`: Main gap-detection logic

#### Modified Functions
- `add_to_scrobble_history()`: Now accepts `source` parameter
- `main()`: Completely rewritten for mobile gap-filling workflow

#### Removed Functions
- `find_new_tracks_to_scrobble()`: Replaced with `process_today_tracks_with_gap_detection()`
- Old timestamp estimation logic removed in favor of "Today"-specific estimation

### Documentation

#### Updated README
- **New Features section**: Added mobile gap-filling details
- **Updated configuration**: Shows all new `.env` options
- **New limitations section**: Clearly documents YouTube Music API constraints
- **Comparison table**: Updated differences from Docker version
- **Dry-run examples**: Added throughout documentation

### Breaking Changes

⚠️ **None** - This release is fully backward compatible:
- Existing `.env` files work (new options have defaults)
- Existing history files work (source field optional)
- Existing cron jobs work (though longer intervals recommended)

### Migration Guide

To take advantage of new features:

1. **Update configuration** (optional):
   ```bash
   # Add to .env file:
   RECENT_WINDOW_HOURS=2
   MAX_SCROBBLES_PER_RUN=20
   ENABLE_MOBILE_DETECTION=true
   DRY_RUN=false
   ```

2. **Test with dry-run**:
   ```bash
   sudo -u ytmusic /opt/ytmusic-scrobbler/venv/bin/python3 /opt/ytmusic-scrobbler/scrobble_oracle.py --dry-run
   ```

3. **Update cron interval** (recommended):
   ```bash
   sudo bash setup_cron.sh 120  # Every 2 hours
   ```

### Known Issues

- **"Today" only**: Bot cannot process tracks from "Yesterday" or older due to timestamp limitations
- **First run**: May miss some tracks - this is expected behavior
- **Mobile overlap**: If mobile extension delays scrobbling, bot may create duplicate (rare)

### Future Plans

- Support for Google Takeout import (for historical scrobbles with exact timestamps)
- Web UI for configuration and monitoring
- Real-time detection using YouTube Music's "currently playing" status
- Better loop detection using pattern analysis

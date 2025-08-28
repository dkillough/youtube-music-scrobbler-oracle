#!/usr/bin/env python3
"""
History management utility for YTMusic Scrobbler
Provides tools to inspect, clean, and manage scrobble history
"""
import json
import time
import datetime
import argparse
from pathlib import Path
from typing import Dict, List

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR / "config"
SCROBBLE_HISTORY_FILE = CONFIG_DIR / "scrobble_history.json"
TWO_WEEKS_SECONDS = 14 * 24 * 60 * 60


def load_history() -> Dict[str, Dict]:
    """Load scrobble history from JSON file"""
    if SCROBBLE_HISTORY_FILE.exists():
        with open(SCROBBLE_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_history(history: Dict[str, Dict]):
    """Save scrobble history to JSON file"""
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(SCROBBLE_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def show_stats(history: Dict[str, Dict]):
    """Display statistics about scrobble history"""
    if not history:
        print("No scrobble history found.")
        return
    
    total_tracks = len(history)
    current_time = int(time.time())
    two_weeks_ago = current_time - TWO_WEEKS_SECONDS
    
    recent_tracks = sum(1 for track in history.values() 
                       if track.get('scrobbled_at', 0) >= two_weeks_ago)
    old_tracks = total_tracks - recent_tracks
    
    # Find date range
    timestamps = [track.get('scrobbled_at', 0) for track in history.values()]
    min_timestamp = min(timestamps) if timestamps else 0
    max_timestamp = max(timestamps) if timestamps else 0
    
    print(f"📊 Scrobble History Statistics")
    print(f"{'='*40}")
    print(f"Total tracks: {total_tracks}")
    print(f"Recent tracks (last 2 weeks): {recent_tracks}")
    print(f"Old tracks (>2 weeks): {old_tracks}")
    
    if min_timestamp and max_timestamp:
        min_date = datetime.datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        max_date = datetime.datetime.fromtimestamp(max_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Date range: {min_date} to {max_date}")
    
    # Top artists
    artists = {}
    unique_tracks = {}
    for scrobble_key, track in history.items():
        artist = track.get('artist', 'Unknown')
        artists[artist] = artists.get(artist, 0) + 1
        
        # Count unique tracks
        track_id = extract_track_id(scrobble_key)
        if track_id not in unique_tracks:
            unique_tracks[track_id] = track
    
    print(f"Unique tracks: {len(unique_tracks)}")
    print(f"Total scrobbles: {total_tracks}")
    
    if artists:
        print(f"\n🎵 Top 10 Artists:")
        sorted_artists = sorted(artists.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (artist, count) in enumerate(sorted_artists, 1):
            print(f"{i:2}. {artist}: {count} tracks")


def list_recent(history: Dict[str, Dict], days: int = 7):
    """List recent scrobbles"""
    if not history:
        print("No scrobble history found.")
        return
    
    cutoff_time = int(time.time()) - (days * 24 * 60 * 60)
    recent_tracks = []
    
    for scrobble_key, track_data in history.items():
        if track_data.get('scrobbled_at', 0) >= cutoff_time:
            recent_tracks.append((scrobble_key, track_data))
    
    if not recent_tracks:
        print(f"No tracks scrobbled in the last {days} days.")
        return
    
    # Sort by timestamp (newest first)
    recent_tracks.sort(key=lambda x: x[1].get('scrobbled_at', 0), reverse=True)
    
    print(f"🕒 Tracks scrobbled in the last {days} days:")
    print(f"{'='*60}")
    
    for scrobble_key, track_data in recent_tracks:
        timestamp = track_data.get('scrobbled_at', 0)
        date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        artist = track_data.get('artist', 'Unknown')
        title = track_data.get('title', 'Unknown')
        album = track_data.get('album', '')
        duration = track_data.get('duration_seconds', 0)
        track_id = extract_track_id(scrobble_key)
        
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
        
        print(f"{date_str} | {artist} - {title} ({duration_str})")
        if album:
            print(f"{'':19} | Album: {album}")
        print(f"{'':19} | YouTube: https://music.youtube.com/watch?v={track_id}")
        print()


def cleanup_old(history: Dict[str, Dict], dry_run: bool = True) -> Dict[str, Dict]:
    """Clean up scrobbles older than two weeks"""
    current_time = int(time.time())
    cutoff_time = current_time - TWO_WEEKS_SECONDS
    
    old_tracks = []
    cleaned_history = {}
    
    for scrobble_key, track_data in history.items():
        if track_data.get('scrobbled_at', 0) >= cutoff_time:
            cleaned_history[scrobble_key] = track_data
        else:
            old_tracks.append((scrobble_key, track_data))
    
    if not old_tracks:
        print("No tracks older than 2 weeks found.")
        return history
    
    print(f"🗑️  Found {len(old_tracks)} tracks older than 2 weeks:")
    print(f"{'='*60}")
    
    for scrobble_key, track_data in old_tracks:
        timestamp = track_data.get('scrobbled_at', 0)
        date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        artist = track_data.get('artist', 'Unknown')
        title = track_data.get('title', 'Unknown')
        print(f"{date_str} | {artist} - {title}")
    
    if dry_run:
        print(f"\n⚠️  This was a dry run. Use --force to actually remove these tracks.")
        return history
    else:
        print(f"\n✅ Removed {len(old_tracks)} old tracks from history.")
        return cleaned_history


def extract_track_id(scrobble_key: str) -> str:
    """Extract track ID from scrobble key (format: track_id_timestamp)"""
    if '_' in scrobble_key:
        return scrobble_key.rsplit('_', 1)[0]
    return scrobble_key


def search_tracks(history: Dict[str, Dict], query: str):
    """Search for tracks in history"""
    if not history:
        print("No scrobble history found.")
        return
    
    query_lower = query.lower()
    matches = []
    
    for scrobble_key, track_data in history.items():
        artist = track_data.get('artist', '').lower()
        title = track_data.get('title', '').lower()
        album = track_data.get('album', '').lower()
        
        if (query_lower in artist or query_lower in title or query_lower in album):
            matches.append((scrobble_key, track_data))
    
    if not matches:
        print(f"No tracks found matching '{query}'")
        return
    
    # Sort by timestamp (newest first)
    matches.sort(key=lambda x: x[1].get('scrobbled_at', 0), reverse=True)
    
    print(f"🔍 Found {len(matches)} scrobbles matching '{query}':")
    print(f"{'='*60}")
    
    for scrobble_key, track_data in matches:
        timestamp = track_data.get('scrobbled_at', 0)
        date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        artist = track_data.get('artist', 'Unknown')
        title = track_data.get('title', 'Unknown')
        album = track_data.get('album', '')
        duration = track_data.get('duration_seconds', 0)
        track_id = extract_track_id(scrobble_key)
        
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
        
        print(f"{date_str} | {artist} - {title} ({duration_str})")
        if album:
            print(f"{'':19} | Album: {album}")
        print(f"{'':19} | YouTube: https://music.youtube.com/watch?v={track_id}")
        print()


def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="YTMusic Scrobbler History Manager")
    parser.add_argument('command', choices=['stats', 'list', 'cleanup', 'search', 'auto-cleanup'],
                       help='Command to execute')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days for list command (default: 7)')
    parser.add_argument('--query', type=str,
                       help='Search query for search command')
    parser.add_argument('--force', action='store_true',
                       help='Actually perform cleanup (not just dry run)')
    
    args = parser.parse_args()
    
    # Load history
    history = load_history()
    
    if args.command == 'stats':
        show_stats(history)
    
    elif args.command == 'list':
        list_recent(history, args.days)
    
    elif args.command == 'cleanup':
        cleaned_history = cleanup_old(history, dry_run=not args.force)
        if args.force and cleaned_history != history:
            save_history(cleaned_history)
    
    elif args.command == 'search':
        if not args.query:
            print("Error: --query is required for search command")
            return
        search_tracks(history, args.query)
    
    elif args.command == 'auto-cleanup':
        # Automatic cleanup (always forces, used by main scrobbler)
        two_weeks_seconds = 14 * 24 * 60 * 60
        current_time = int(time.time())
        cutoff_time = current_time - two_weeks_seconds
        
        cleaned_history = {}
        removed_count = 0
        
        for scrobble_key, track_data in history.items():
            if track_data.get('scrobbled_at', 0) >= cutoff_time:
                cleaned_history[scrobble_key] = track_data
            else:
                removed_count += 1
        
        if removed_count > 0:
            save_history(cleaned_history)
            print(f"🗑️  Automatically cleaned up {removed_count} old scrobble records")
            print(f"📊 Kept {len(cleaned_history)} recent records (last 2 weeks)")
        else:
            print(f"✅ No cleanup needed - all {len(history)} records are recent")
        
        # Show storage info
        original_size = len(str(history))
        cleaned_size = len(str(cleaned_history))
        saved_bytes = original_size - cleaned_size
        
        if saved_bytes > 0:
            if saved_bytes > 1024:
                saved_kb = saved_bytes / 1024
                print(f"💾 Saved approximately {saved_kb:.1f} KB of storage")
            else:
                print(f"💾 Saved approximately {saved_bytes} bytes of storage")


if __name__ == "__main__":
    main()
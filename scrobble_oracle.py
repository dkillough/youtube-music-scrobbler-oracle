#!/usr/bin/env python3
"""
Oracle Cloud version of YTMusic Scrobbler
Runs as a periodic script instead of continuous Docker container
"""
import time
import os
import datetime
from datetime import date
import logging
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import pylast
import ytmusicapi.exceptions
from ytmusicapi import YTMusic
from fuzzywuzzy import fuzz

# Configuration paths for Oracle Cloud
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)

# Ensure config directory exists
if not CONFIG_DIR.exists():
    print(f"Creating config directory: {CONFIG_DIR}")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables from .env file if it exists
env_file = SCRIPT_DIR / ".env"
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Environment configuration
LASTFM_API_KEY = os.environ.get('LASTFM_API_KEY')
LASTFM_API_SECRET = os.environ.get('LASTFM_API_SECRET')
LASTFM_USERNAME = os.environ.get('LASTFM_USERNAME')
LASTFM_PASSWORD = os.environ.get('LASTFM_PASSWORD')

# Validate required environment variables
if not all([LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME, LASTFM_PASSWORD]):
    print("ERROR: Missing required Last.fm environment variables:")
    print("Please set: LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME, LASTFM_PASSWORD")
    sys.exit(1)

# Mobile gap-filling configuration
RECENT_WINDOW_HOURS = int(os.environ.get('RECENT_WINDOW_HOURS', '2'))
MAX_SCROBBLES_PER_RUN = int(os.environ.get('MAX_SCROBBLES_PER_RUN', '20'))
ENABLE_MOBILE_DETECTION = os.environ.get('ENABLE_MOBILE_DETECTION', 'true').lower() == 'true'
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'

# Check for --dry-run command line argument
if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
    DRY_RUN = True

# File paths
BROWSER_CONFIG = CONFIG_DIR / "browser.json"
HISTORY_FILE = CONFIG_DIR / "history.txt"  # Legacy single track ID file
SCROBBLE_HISTORY_FILE = CONFIG_DIR / "scrobble_history.json"  # Comprehensive scrobble history
ERROR_CREDS_FILE = CONFIG_DIR / "erroredcreds.json"

# Configuration constants
TWO_WEEKS_SECONDS = 14 * 24 * 60 * 60  # 14 days in seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(CONFIG_DIR / "scrobble.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def login_to_ytmusic():
    """Login to YouTube Music using saved credentials"""
    try:
        if not BROWSER_CONFIG.exists():
            logger.error("Browser config file not found. Please run setup first.")
            return None
            
        ytmusic = YTMusic(str(BROWSER_CONFIG))
        logger.info("Successfully logged into YouTube Music")
        return ytmusic
        
    except ytmusicapi.exceptions.YTMusicServerError as e:
        logger.warning(f"YouTube Music server error: {e}")
        # Mark credentials as errored
        if BROWSER_CONFIG.exists():
            BROWSER_CONFIG.rename(ERROR_CREDS_FILE)
        logger.error("Credentials may have expired. Please run setup again.")
        return None
        
    except Exception as e:
        logger.error(f"Failed to login to YouTube Music: {e}")
        return None


def get_listening_history(ytmusic):
    """Get the current listening history from YouTube Music"""
    try:
        history = ytmusic.get_history()
        if history:
            logger.info(f"Retrieved {len(history)} tracks from history")
            return history
        else:
            logger.warning("No history retrieved")
            return []

    except ytmusicapi.exceptions.YTMusicServerError as e:
        logger.error(f"Failed to get history: {e}")
        # Mark credentials as errored
        if BROWSER_CONFIG.exists():
            BROWSER_CONFIG.rename(ERROR_CREDS_FILE)
        return None

    except Exception as e:
        logger.error(f"Unexpected error getting history: {e}")
        return None


def get_lastfm_recent_scrobbles(network: pylast.LastFMNetwork, hours: int = 2) -> Dict[str, List[int]]:
    """
    Fetch recent scrobbles from Last.fm within the specified time window.
    Returns a dictionary mapping normalized (artist, title) to list of timestamps.
    """
    try:
        # Calculate time window
        current_time = int(time.time())
        from_timestamp = current_time - (hours * 3600)

        logger.info(f"Fetching Last.fm scrobbles from last {hours} hours...")

        # Get user's recent tracks
        user = network.get_user(LASTFM_USERNAME)
        recent_tracks = user.get_recent_tracks(
            limit=200,  # Get up to 200 tracks
            time_from=from_timestamp,
            time_to=current_time
        )

        # Build lookup dictionary with normalized track info
        scrobble_map = {}
        count = 0
        currently_playing = None

        for track in recent_tracks:
            try:
                # Extract track info
                artist_obj = track.track.artist
                artist_name = artist_obj.get_name() if artist_obj else ""
                track_name = track.track.get_name() if track.track else ""

                if not artist_name or not track_name:
                    continue

                # Check for "now playing" track
                if hasattr(track, 'playback_status') and track.playback_status == 'now playing':
                    currently_playing = (artist_name, track_name)
                    logger.info(f"Currently playing on Last.fm: {artist_name} - {track_name}")
                    continue

                # Get timestamp
                timestamp = int(track.timestamp) if hasattr(track, 'timestamp') and track.timestamp else None
                if not timestamp:
                    continue

                # Normalize artist and title for matching
                normalized_artist = normalize_text(artist_name, is_artist=True)
                normalized_title = normalize_text(track_name, is_artist=False)
                key = (normalized_artist, normalized_title)

                # Add to map
                if key not in scrobble_map:
                    scrobble_map[key] = []
                scrobble_map[key].append(timestamp)
                count += 1

            except Exception as e:
                logger.warning(f"Error processing Last.fm track: {e}")
                continue

        logger.info(f"Found {count} scrobbles on Last.fm in recent window ({len(scrobble_map)} unique tracks)")
        if currently_playing:
            logger.info(f"Note: Currently playing track detected: {currently_playing[0]} - {currently_playing[1]}")

        return scrobble_map

    except Exception as e:
        logger.error(f"Failed to fetch Last.fm recent scrobbles: {e}")
        logger.warning("Continuing without Last.fm cross-reference (mobile detection disabled for this run)")
        return {}


def load_scrobble_history() -> Dict[str, Dict]:
    """Load comprehensive scrobble history from JSON file"""
    try:
        if SCROBBLE_HISTORY_FILE.exists():
            with open(SCROBBLE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                logger.info(f"Loaded {len(history)} tracks from scrobble history")
                return history
        else:
            logger.info("No scrobble history file found, starting fresh")
            return {}
    except Exception as e:
        logger.error(f"Error loading scrobble history: {e}")
        return {}


def save_scrobble_history(history: Dict[str, Dict]):
    """Save comprehensive scrobble history to JSON file"""
    try:
        with open(SCROBBLE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(history)} tracks to scrobble history")
    except Exception as e:
        logger.error(f"Error saving scrobble history: {e}")


def cleanup_old_history(history: Dict[str, Dict]) -> Dict[str, Dict]:
    """Remove scrobble records older than two weeks"""
    current_time = int(time.time())
    cutoff_time = current_time - TWO_WEEKS_SECONDS

    cleaned_history = {}
    removed_count = 0

    for scrobble_key, track_data in history.items():
        # Handle both old timestamp-based keys and new date-based keys
        scrobbled_at = track_data.get('scrobbled_at', 0)

        if scrobbled_at >= cutoff_time:
            cleaned_history[scrobble_key] = track_data
        else:
            removed_count += 1

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old scrobble records")

    return cleaned_history


def get_last_scrobbled():
    """Get the ID of the last scrobbled track (legacy compatibility)"""
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                last_id = f.read().strip()
                logger.info(f"Legacy last scrobbled track ID: {last_id}")
                return last_id
        else:
            logger.info("No legacy scrobble history found")
            return ""
    except Exception as e:
        logger.error(f"Error reading legacy history file: {e}")
        return ""


def save_last_scrobbled(track_id):
    """Save the ID of the last scrobbled track (legacy compatibility)"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            f.write(track_id)
        logger.info(f"Saved legacy last scrobbled track ID: {track_id}")
    except Exception as e:
        logger.error(f"Error saving legacy history file: {e}")


def get_last_processed_track_id() -> str:
    """Get the last processed track ID from legacy history file"""
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                track_id = f.read().strip()
                if track_id:
                    logger.info(f"Last processed track ID: {track_id}")
                    return track_id
        logger.info("No previous processing history found")
        return None
    except Exception as e:
        logger.error(f"Error reading last processed track ID: {e}")
        return None


def save_last_processed_track_id(track_id: str):
    """Save the most recent processed track ID (even if not successfully scrobbled)"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            f.write(track_id)
        logger.info(f"Updated last processed track ID: {track_id}")
    except Exception as e:
        logger.error(f"Error saving last processed track ID: {e}")


def safe_get_artist_name(track: Dict) -> str:
    """Safely extract artist name from YouTube Music track with null safety"""
    try:
        if not track:
            return "Unknown Artist"

        artists = track.get('artists')
        if not artists or not isinstance(artists, list) or len(artists) == 0:
            return "Unknown Artist"

        artist_obj = artists[0]
        if not artist_obj or not isinstance(artist_obj, dict):
            return "Unknown Artist"

        artist_name = artist_obj.get('name', 'Unknown Artist')
        return artist_name if artist_name else "Unknown Artist"

    except Exception as e:
        logger.warning(f"Error extracting artist name: {e}")
        return "Unknown Artist"


def safe_get_title(track: Dict) -> str:
    """Safely extract title from YouTube Music track with null safety"""
    try:
        if not track:
            return "Unknown Title"

        title = track.get('title', 'Unknown Title')
        return title if title else "Unknown Title"

    except Exception as e:
        logger.warning(f"Error extracting title: {e}")
        return "Unknown Title"


def safe_get_album_name(track: Dict) -> str:
    """Safely extract album name from YouTube Music track with null safety"""
    try:
        if not track:
            return ""

        album = track.get('album')
        if not album:
            return ""

        # Handle case where album is not a dict
        if not isinstance(album, dict):
            logger.warning(f"Album is not a dict, got: {type(album)}")
            return ""

        album_name = album.get('name', '')
        return album_name if album_name else ""

    except Exception as e:
        logger.warning(f"Error extracting album name: {e}")
        return ""


def clean_youtube_metadata(text: str, is_artist: bool = False) -> str:
    """Clean YouTube Music specific metadata issues"""
    if not text:
        return ""
    
    text = text.strip()
    
    # Remove YouTube-specific suffixes
    youtube_suffixes = [
        r'\s*-\s*Topic$',
        r'\s*VEVO$', 
        r'\s*Records$',
        r'\s*Music$',
        r'\s*Official$',
    ]
    
    for suffix in youtube_suffixes:
        text = re.sub(suffix, '', text, flags=re.IGNORECASE)

    # Clean up common YouTube title additions (for titles, not artists)
    if not is_artist:
        # Remove ALL content within square brackets (e.g., [Remaster], [Live], [Audio], etc.)
        text = re.sub(r'\s*\[.*?\]\s*', ' ', text)

        title_cleanups = [
            # End-of-string patterns (original behavior)
            r'\s*\(Official Video\)$',
            r'\s*\(Official Audio\)$',
            r'\s*\(Official Music Video\)$',
            r'\s*\(Lyric Video\)$',
            r'\s*\(Lyrics\)$',
            r'\s*\[Official Video\]$',
            r'\s*\[Official Audio\]$',
            r'\s*\[Lyric Video\]$',
            r'\s*\[Lyrics\]$',
            r'\s*\(HD\)$',
            r'\s*\[HD\]$',
            r'\s*\(4K\)$',
            r'\s*\[4K\]$',
            # Middle-of-string patterns (for cases like "Song (Official Video) feat. Artist")
            r'\s*\(Official Video\)\s+',
            r'\s*\(Official Audio\)\s+',
            r'\s*\(Official Music Video\)\s+',
            r'\s*\(Lyric Video\)\s+',
            r'\s*\(Lyrics\)\s+',
            r'\s*\[Official Video\]\s+',
            r'\s*\[Official Audio\]\s+',
            r'\s*\[Lyric Video\]\s+',
            r'\s*\[Lyrics\]\s+',
            r'\s*\(HD\)\s+',
            r'\s*\[HD\]\s+',
            r'\s*\(4K\)\s+',
            r'\s*\[4K\]\s+',
        ]

        # First handle end-of-string patterns (remove completely)
        end_patterns = title_cleanups[:13]  # First 13 are end patterns
        for cleanup in end_patterns:
            text = re.sub(cleanup, '', text, flags=re.IGNORECASE)

        # Then handle middle-of-string patterns (replace with single space)
        middle_patterns = title_cleanups[13:]  # Remaining are middle patterns
        for cleanup in middle_patterns:
            text = re.sub(cleanup, ' ', text, flags=re.IGNORECASE)

    return text.strip()


def normalize_featuring_artists(text: str) -> str:
    """Normalize featuring artist variations"""
    if not text:
        return ""

    # Comprehensive featuring variations - preserve surrounding whitespace
    featuring_patterns = [
        (r'\bfeaturing\b', 'feat.'),  # Exact word "featuring"
        (r'\bfeat\b(?!\.)', 'feat.'),  # "feat" without period (add period)
        (r'\bft\.', 'feat.'),          # "ft." with period
        (r'\bft\b(?!\.)', 'feat.'),    # "ft" without period
        (r'\bwith\b', 'feat.'),        # "with" as exact word
        (r'\bx\b', 'feat.'),           # "x" as exact word (common in hip-hop/rap)
        (r'\bversus\b', 'feat.'),      # "versus" as exact word
        (r'\bvs\.', 'feat.'),          # "vs." with period
        (r'\bvs\b(?!\.)', 'feat.'),    # "vs" without period
        (r'\band\b', 'feat.'),         # "and" as exact word (only in featuring context)
        (r'&', 'feat.'),               # "&" symbol (common in collaborations)
    ]

    # Replace all variations with consistent "feat." (preserving whitespace)
    for pattern, replacement in featuring_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Clean up multiple feat. occurrences
    text = re.sub(r'\bfeat\.\s+feat\.', 'feat.', text, flags=re.IGNORECASE)

    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def normalize_remix_versions(text: str) -> str:
    """Normalize remix and version information"""
    if not text:
        return ""

    # Only remove truly redundant tags like "Original Mix"
    # Preserve all other version information exactly as-is to match Last.fm
    text = re.sub(r'\s*\(Original Mix\)', '', text, flags=re.IGNORECASE)

    return text.strip()


def normalize_text(text: str, is_artist: bool = False) -> str:
    """Enhanced text normalization with YouTube-specific cleanup"""
    if not text:
        return ""
    
    # Step 1: Clean YouTube-specific metadata
    text = clean_youtube_metadata(text, is_artist)
    
    # Step 2: Normalize featuring artists (for both artist and title)
    text = normalize_featuring_artists(text)
    
    # Step 3: Handle remix/version info (mainly for titles)
    if not is_artist:
        text = normalize_remix_versions(text)
    
    # Step 4: Convert to lowercase and basic cleanup
    text = text.lower().strip()
    
    # Step 5: Replace common symbol variations
    symbol_replacements = {
        r'\b&\b': 'and',
        r'\+': 'and',
        r'\s+': ' ',  # Multiple spaces to single space
    }
    
    for pattern, replacement in symbol_replacements.items():
        text = re.sub(pattern, replacement, text)
    
    # Step 6: Remove excessive punctuation but keep some meaningful ones
    # Keep: apostrophes, hyphens in words, parentheses for versions
    text = re.sub(r'[^\w\s\'-]', ' ', text)
    text = re.sub(r'\s+', ' ', text)  # Clean up spaces again
    
    return text.strip()


def clean_track_metadata(artist: str, title: str, album: str = "") -> tuple[str, str, str]:
    """Clean and normalize track metadata for better matching"""
    # Clean each field
    cleaned_artist = clean_youtube_metadata(artist, is_artist=True)
    cleaned_title = clean_youtube_metadata(title, is_artist=False) 
    cleaned_album = clean_youtube_metadata(album, is_artist=False)
    
    # Apply featuring normalization to both artist and title
    cleaned_artist = normalize_featuring_artists(cleaned_artist)
    cleaned_title = normalize_featuring_artists(cleaned_title)
    
    # Apply remix/version normalization to title
    cleaned_title = normalize_remix_versions(cleaned_title)
    
    # Log if significant changes were made
    changes = []
    if cleaned_artist != artist:
        changes.append(f"Artist: '{artist}' → '{cleaned_artist}'")
    if cleaned_title != title:
        changes.append(f"Title: '{title}' → '{cleaned_title}'")
    if cleaned_album != album and album:
        changes.append(f"Album: '{album}' → '{cleaned_album}'")
    
    if changes:
        logger.info(f"Cleaned metadata: {', '.join(changes)}")
    
    return cleaned_artist, cleaned_title, cleaned_album


def search_lastfm_tracks(network: pylast.LastFMNetwork, artist: str, title: str, limit: int = 10) -> List[Tuple[pylast.Track, float]]:
    """Search for tracks on Last.fm and return with similarity scores"""
    try:
        # Search for tracks by artist and title
        results = network.search_for_track(artist, title)
        tracks_with_scores = []
        
        normalized_search_artist = normalize_text(artist, is_artist=True)
        normalized_search_title = normalize_text(title, is_artist=False)
        search_string = f"{normalized_search_artist} {normalized_search_title}"
        
        for track in results.get_next_page()[:limit]:
            try:
                artist_obj = track.get_artist()
                artist_name = artist_obj.get_name() if artist_obj else ""
                track_name = track.get_name() if track.get_name() else ""
                
                # Skip if we can't get basic track info
                if not artist_name or not track_name:
                    logger.warning(f"Skipping track with missing artist or title info")
                    continue
                
                track_artist = normalize_text(artist_name, is_artist=True)
                track_title = normalize_text(track_name, is_artist=False)
                track_string = f"{track_artist} {track_title}"
                
                # Calculate similarity score
                similarity = fuzz.ratio(search_string, track_string)
                tracks_with_scores.append((track, similarity))
                
            except Exception as e:
                logger.warning(f"Error processing track result: {e}")
                continue
        
        # Sort by similarity score (descending)
        tracks_with_scores.sort(key=lambda x: x[1], reverse=True)
        return tracks_with_scores
        
    except Exception as e:
        logger.warning(f"Error searching Last.fm tracks: {e}")
        return []


def get_track_popularity(track: pylast.Track) -> int:
    """Get track popularity (listener count) from Last.fm"""
    try:
        listeners = track.get_listener_count()
        return int(listeners) if listeners else 0
    except Exception as e:
        logger.warning(f"Could not get listener count for {track}: {e}")
        return 0


def find_best_track_match(network: pylast.LastFMNetwork, artist: str, title: str, album: str = "", original_artist: str = "", original_title: str = "") -> Optional[pylast.Track]:
    """Find the best matching track on Last.fm using fuzzy matching and popularity"""
    logger.info(f"Searching for best match: {artist} - {title}")
    
    # Search for potential matches using cleaned metadata
    candidates = search_lastfm_tracks(network, artist, title, limit=15)
    
    # If no good candidates and we have original metadata, try with original as fallback
    if not candidates and original_artist and original_title:
        logger.info(f"No matches with cleaned metadata, trying original: {original_artist} - {original_title}")
        candidates = search_lastfm_tracks(network, original_artist, original_title, limit=15)
        if candidates:
            logger.info(f"Found {len(candidates)} candidates using original metadata")
    
    if not candidates:
        logger.warning(f"No Last.fm matches found for: {artist} - {title}")
        return None
    
    # Filter candidates with good similarity scores (>= 80)
    good_candidates = [(track, score) for track, score in candidates if score >= 80]
    
    if not good_candidates:
        # If no good matches, take the best available match if it's reasonable (>= 60)
        best_candidate = candidates[0]
        if best_candidate[1] >= 60:
            logger.info(f"Using best available match (score: {best_candidate[1]})")
            good_candidates = [best_candidate]
        else:
            logger.warning(f"No reasonable matches found (best score: {best_candidate[1]})")
            return None
    
    logger.info(f"Found {len(good_candidates)} good candidates")
    
    # Get popularity for each good candidate
    candidates_with_popularity = []
    for track, similarity_score in good_candidates:
        try:
            popularity = get_track_popularity(track)
            candidates_with_popularity.append((track, similarity_score, popularity))
            
            try:
                artist_obj = track.get_artist()
                artist_name = artist_obj.get_name() if artist_obj else "Unknown Artist"
                track_name = track.get_name() if track.get_name() else "Unknown Track"
                logger.info(f"Candidate: {artist_name} - {track_name} (similarity: {similarity_score}, listeners: {popularity})")
            except Exception as track_info_error:
                logger.warning(f"Error getting track info for candidate: {track_info_error}")
                continue
            
        except Exception as e:
            logger.warning(f"Error getting popularity for track: {e}")
            continue
    
    if not candidates_with_popularity:
        logger.warning("No candidates with valid popularity data")
        return None
    
    # Select best match based on weighted score:
    # 70% similarity + 30% normalized popularity
    max_popularity = max(pop for _, _, pop in candidates_with_popularity) if candidates_with_popularity else 1
    
    best_track = None
    best_weighted_score = -1
    
    for track, similarity_score, popularity in candidates_with_popularity:
        # Normalize popularity (0-100 scale)
        normalized_popularity = (popularity / max_popularity * 100) if max_popularity > 0 else 0
        
        # Weighted score: 70% similarity, 30% popularity
        weighted_score = (similarity_score * 0.7) + (normalized_popularity * 0.3)
        
        if weighted_score > best_weighted_score:
            best_weighted_score = weighted_score
            best_track = track
    
    if best_track:
        try:
            artist_obj = best_track.get_artist()
            artist_name = artist_obj.get_name() if artist_obj else "Unknown Artist"
            track_name = best_track.get_name() if best_track.get_name() else "Unknown Track"
            popularity = next(pop for t, _, pop in candidates_with_popularity if t == best_track)
            logger.info(f"Selected best match: {artist_name} - {track_name} (weighted score: {best_weighted_score:.1f}, listeners: {popularity})")
        except Exception as e:
            logger.warning(f"Error getting best match details: {e}")
    
    return best_track


def scrobble_track(network, track, custom_timestamp: Optional[int] = None) -> bool:
    """Scrobble a single track to Last.fm with enhanced metadata cleanup and fuzzy matching"""
    try:
        # Extract original metadata with safe null checks
        original_artist = safe_get_artist_name(track)
        original_title = safe_get_title(track)
        original_album = safe_get_album_name(track)
        timestamp = custom_timestamp or int(time.time())
        
        # Clean metadata for better matching
        cleaned_artist, cleaned_title, cleaned_album = clean_track_metadata(
            original_artist, original_title, original_album
        )
        
        # Find best matching track on Last.fm using cleaned metadata with fallback to original
        best_track = find_best_track_match(
            network, cleaned_artist, cleaned_title, cleaned_album,
            original_artist, original_title
        )
        
        if best_track:
            # Use the matched track's details with null safety
            try:
                artist_obj = best_track.get_artist()
                matched_artist = artist_obj.get_name() if artist_obj else cleaned_artist
                matched_title = best_track.get_name() if best_track.get_name() else cleaned_title
                
                # Try to get album from the matched track, fallback to cleaned album
                album_obj = best_track.get_album()
                matched_album = album_obj.get_name() if album_obj else cleaned_album
            except Exception as e:
                logger.warning(f"Error extracting track details from Last.fm match: {e}")
                matched_artist = cleaned_artist
                matched_title = cleaned_title
                matched_album = cleaned_album
            
            logger.info(f"Scrobbling matched track: {matched_artist} - {matched_title}")
            if matched_artist != cleaned_artist or matched_title != cleaned_title:
                logger.info(f"Cleaned input: {cleaned_artist} - {cleaned_title}")
            if cleaned_artist != original_artist or cleaned_title != original_title:
                logger.info(f"Original YTMusic: {original_artist} - {original_title}")
            
            network.scrobble(matched_artist, matched_title, timestamp, matched_album)
        else:
            # Fallback to cleaned track details (better than raw YouTube data)
            logger.warning(f"No good match found, using cleaned metadata: {cleaned_artist} - {cleaned_title}")
            if cleaned_artist != original_artist or cleaned_title != original_title:
                logger.info(f"Original YTMusic: {original_artist} - {original_title}")
            network.scrobble(cleaned_artist, cleaned_title, timestamp, cleaned_album)
        
        # Format timestamp for logging
        timestamp_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Scrobbled successfully at {timestamp_str}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to scrobble track: {e}")
        return False


def get_track_duration_seconds(track: Dict) -> int:
    """Extract track duration in seconds from YouTube Music track data"""
    try:
        # Try to get duration from the track data
        duration_text = track.get('duration', '')
        if duration_text:
            # Parse duration like "3:45" or "1:23:45"
            parts = duration_text.split(':')
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
        
        # Fallback: estimate based on duration_seconds if available
        duration_seconds = track.get('duration_seconds')
        if duration_seconds:
            return int(duration_seconds)
        
        # Default fallback: assume 3.5 minutes for unknown duration
        logger.warning(f"Could not determine duration for track, using default 210 seconds")
        return 210
        
    except Exception as e:
        logger.warning(f"Error parsing track duration: {e}, using default 210 seconds")
        return 210


def add_to_scrobble_history(track: Dict, timestamp: int, source: str = "ytmusic_bot") -> None:
    """Add a track to the comprehensive scrobble history with source tracking"""
    track_id = track['videoId']
    duration_seconds = get_track_duration_seconds(track)

    track_data = {
        'artist': safe_get_artist_name(track),
        'title': safe_get_title(track),
        'album': safe_get_album_name(track),
        'scrobbled_at': timestamp,
        'duration_seconds': duration_seconds,
        'source': source,  # Track source: "ytmusic_bot" or "mobile_extension"
        'youtube_url': f"https://music.youtube.com/watch?v={track_id}"
    }

    # Load existing history
    history = load_scrobble_history()

    # Create a unique key for this scrobble using date + counter
    # This allows multiple scrobbles per day while preventing duplicates from multiple cron runs
    scrobble_date = date.fromtimestamp(timestamp).isoformat()  # e.g., "2025-12-20"

    # Count how many times this track was already scrobbled today
    today_count = 0
    prefix = f"{track_id}_{scrobble_date}"
    for key in history.keys():
        if key.startswith(prefix):
            today_count += 1

    # Generate new counter (1-indexed)
    counter = today_count + 1
    scrobble_key = f"{track_id}_{scrobble_date}_{counter}"

    logger.info(f"Recording scrobble #{counter} for track {track_id} on {scrobble_date}")

    # Add new track with unique key
    history[scrobble_key] = track_data

    # Clean up old entries and save
    cleaned_history = cleanup_old_history(history)
    save_scrobble_history(cleaned_history)


def get_track_scrobble_timestamps(track_id: str, scrobble_history: Dict[str, Dict]) -> List[int]:
    """Get all timestamps when a specific track was scrobbled"""
    timestamps = []
    for scrobble_key, scrobble_data in scrobble_history.items():
        # Extract track_id from scrobble_key
        # Supports both old (track_id_date) and new (track_id_date_counter) formats
        if scrobble_key.startswith(f"{track_id}_"):
            timestamps.append(scrobble_data['scrobbled_at'])
    return sorted(timestamps)


def can_scrobble_track(track: Dict, proposed_timestamp: int, scrobble_history: Dict[str, Dict]) -> Tuple[bool, str]:
    """Check if a track can be scrobbled at the proposed timestamp"""
    track_id = track['videoId']
    track_duration = get_track_duration_seconds(track)
    
    # Get all previous scrobbles of this track
    previous_timestamps = get_track_scrobble_timestamps(track_id, scrobble_history)
    
    if not previous_timestamps:
        return True, "No previous scrobbles found"
    
    # Check if proposed timestamp has sufficient gap from any previous scrobble
    min_gap_required = track_duration + 30  # Track length + 30 seconds buffer
    
    for prev_timestamp in previous_timestamps:
        time_gap = abs(proposed_timestamp - prev_timestamp)
        if time_gap < min_gap_required:
            gap_minutes = time_gap // 60
            required_minutes = min_gap_required // 60
            return False, f"Too close to previous scrobble ({gap_minutes}m gap, need {required_minutes}m)"
    
    return True, f"Sufficient gap from {len(previous_timestamps)} previous scrobbles"


def find_new_tracks_to_scrobble(ytmusic_history: List[Dict], scrobble_history: Dict[str, Dict], last_processed_track_id: str = None) -> List[Tuple[Dict, int]]:
    """Find only NEW tracks that haven't been processed yet"""
    tracks_to_scrobble = []
    current_time = int(time.time())
    new_tracks_found = False
    
    logger.info(f"Checking for new tracks since last run...")
    
    # Find where we left off by looking for the last processed track
    start_index = 0
    if last_processed_track_id:
        for i, track in enumerate(ytmusic_history):
            if track['videoId'] == last_processed_track_id:
                start_index = i + 1  # Start after the last processed track
                logger.info(f"Resuming from track #{i+1}, found {start_index} new tracks to check")
                break
        else:
            logger.info(f"Last processed track not found in current history, processing all {len(ytmusic_history)} tracks")
    else:
        logger.info(f"No previous processing history, checking all {len(ytmusic_history)} tracks")
    
    # Only process NEW tracks (from start_index forward)
    new_tracks = ytmusic_history[start_index:]
    if not new_tracks:
        logger.info("No new tracks found since last run")
        return []
    
    logger.info(f"Found {len(new_tracks)} new tracks to process")
    
    # Process new tracks in reverse order (oldest first) with realistic timestamps
    for i, track in enumerate(reversed(new_tracks)):
        track_id = track['videoId']
        artist = safe_get_artist_name(track)
        title = safe_get_title(track)
        
        # Create realistic timestamp: track duration + 30s buffer minimum, working backwards
        track_duration = get_track_duration_seconds(track)
        track_spacing = max(track_duration + 30, 180)  # At least 3 minutes between any tracks
        
        # Calculate cumulative time going backwards
        minutes_back = (len(new_tracks) - i - 1) * (track_spacing // 60)
        proposed_timestamp = current_time - (minutes_back * 60)
        
        # Check if this track was already scrobbled recently (within last 24 hours)
        can_scrobble, reason = can_scrobble_track_simple(track, proposed_timestamp, scrobble_history)
        
        if can_scrobble:
            tracks_to_scrobble.append((track, proposed_timestamp))
            logger.info(f"✅ NEW: {artist} - {title}: {reason}")
        else:
            logger.info(f"⏭️  SKIP: {artist} - {title}: {reason}")
    
    logger.info(f"Found {len(tracks_to_scrobble)} new tracks ready to scrobble")
    return tracks_to_scrobble


def can_scrobble_track_simple(track: Dict, proposed_timestamp: int, scrobble_history: Dict[str, Dict]) -> Tuple[bool, str]:
    """Smart duplicate checking - prevent scrobbling same track too close based on track length"""
    track_id = track['videoId']
    track_duration = get_track_duration_seconds(track)

    # Minimum gap: track duration + 30 seconds (allows for loops/repeats)
    min_gap_seconds = track_duration + 30
    cutoff_time = proposed_timestamp - min_gap_seconds

    if track_id in scrobble_history:
        for timestamp_str in scrobble_history[track_id]:
            timestamp = int(timestamp_str)
            if timestamp > cutoff_time:
                minutes_ago = (proposed_timestamp - timestamp) // 60
                min_gap_minutes = min_gap_seconds // 60
                return False, f"Already scrobbled {minutes_ago}m ago (need {min_gap_minutes}m gap for this track)"

    return True, "Track ready to scrobble"


def extract_today_tracks(ytmusic_history: List[Dict]) -> List[Dict]:
    """
    Extract tracks from recent history based on RECENT_WINDOW_HOURS.
    YouTube Music history doesn't provide exact timestamps, just relative dates.
    We extract based on the configured time window.
    """
    recent_tracks = []

    # Determine which sections to include based on RECENT_WINDOW_HOURS
    include_sections = ['today']

    if RECENT_WINDOW_HOURS >= 24:  # 1+ days
        include_sections.append('yesterday')

    if RECENT_WINDOW_HOURS >= 48:  # 2+ days
        include_sections.append('this week')

    logger.info(f"Extracting tracks from sections: {include_sections} (RECENT_WINDOW_HOURS={RECENT_WINDOW_HOURS})")

    for track in ytmusic_history:
        # YouTube Music history items may have a 'played' field
        played_info = track.get('played', '')

        # Convert to lowercase for case-insensitive matching
        played_info_lower = played_info.lower() if played_info else 'today'

        # Check if this track's section should be included
        should_include = False
        for section in include_sections:
            if section.lower() in played_info_lower:
                should_include = True
                break

        # If no played info exists, assume it's recent (today)
        if not track.get('played'):
            should_include = True

        if should_include:
            recent_tracks.append(track)
        # Continue processing all tracks within the time window (don't break early)

    logger.info(f"Extracted {len(recent_tracks)} tracks from recent history ({RECENT_WINDOW_HOURS}h window)")
    return recent_tracks


def is_track_in_lastfm_recent(track: Dict, lastfm_scrobbles: Dict[str, List[int]]) -> Tuple[bool, Optional[int]]:
    """
    Check if a track exists in Last.fm recent scrobbles.
    Returns (found, most_recent_timestamp) tuple.
    """
    if not lastfm_scrobbles:
        return False, None

    # Normalize track metadata with safe extraction
    original_artist = safe_get_artist_name(track)
    original_title = safe_get_title(track)

    # Clean and normalize for matching
    cleaned_artist, cleaned_title, _ = clean_track_metadata(original_artist, original_title, "")
    normalized_artist = normalize_text(cleaned_artist, is_artist=True)
    normalized_title = normalize_text(cleaned_title, is_artist=False)

    key = (normalized_artist, normalized_title)

    if key in lastfm_scrobbles:
        timestamps = lastfm_scrobbles[key]
        most_recent = max(timestamps) if timestamps else None
        return True, most_recent

    return False, None


def process_today_tracks_with_gap_detection(
    today_tracks: List[Dict],
    lastfm_scrobbles: Dict[str, List[int]],
    scrobble_history: Dict[str, Dict],
    max_tracks: int = 20
) -> List[Tuple[Dict, int]]:
    """
    Process 'Today' tracks with mobile gap detection.
    Returns list of (track, estimated_timestamp) tuples for tracks that should be scrobbled.
    """
    tracks_to_scrobble = []
    current_time = int(time.time())
    cumulative_offset = 0

    logger.info(f"Processing {len(today_tracks)} tracks from 'Today' with mobile gap detection...")
    logger.info("="*60)

    # Track pending scrobbles in this run to avoid duplicates
    pending_scrobbles_count = {}

    for i, track in enumerate(reversed(today_tracks)):  # Process oldest to newest
        track_id = track['videoId']
        artist = safe_get_artist_name(track)
        title = safe_get_title(track)
        duration = get_track_duration_seconds(track)

        # Estimate timestamp working backwards from current time
        estimated_timestamp = current_time - cumulative_offset
        cumulative_offset += duration + 30  # Track duration + 30s buffer

        # Don't go back more than 24 hours
        if cumulative_offset > 86400:
            logger.info(f"  ⏸️  Stopping: Reached 24-hour limit")
            break

        # Check against Last.fm recent scrobbles (mobile detection)
        found_in_lastfm, lastfm_timestamp = is_track_in_lastfm_recent(track, lastfm_scrobbles)

        if found_in_lastfm and ENABLE_MOBILE_DETECTION:
            time_diff_minutes = abs(estimated_timestamp - lastfm_timestamp) // 60 if lastfm_timestamp else 0
            logger.info(f"  ✓ {artist} - {title}")
            logger.info(f"    └─ Found on Last.fm (~{time_diff_minutes}m difference), skipping (mobile scrobble)")
            continue

        # Check against local bot history using counter-based approach
        # Count how many times this track appears in YouTube history vs our scrobble history
        scrobble_date = date.today().isoformat()  # e.g., "2025-12-20"

        # Count occurrences in YouTube Music history (today_tracks)
        youtube_count = sum(1 for t in today_tracks if t.get('videoId') == track_id)

        # Count how many times already scrobbled today in our history
        prefix = f"{track_id}_{scrobble_date}"
        already_scrobbled_count = sum(1 for key in scrobble_history.keys() if key.startswith(prefix))

        # Add pending scrobbles from current run
        current_pending = pending_scrobbles_count.get(track_id, 0)
        total_scrobbled = already_scrobbled_count + current_pending

        # Skip if we've already scrobbled (or are about to scrobble) all occurrences
        if total_scrobbled >= youtube_count:
            logger.info(f"  ✓ {artist} - {title}")
            logger.info(f"    └─ Already scrobbled/queued {youtube_count} occurrence(s) today, skipping")
            continue

        # Track is clear to scrobble!
        tracks_to_scrobble.append((track, estimated_timestamp))
        pending_scrobbles_count[track_id] = current_pending + 1
        timestamp_str = datetime.datetime.fromtimestamp(estimated_timestamp).strftime('%H:%M:%S')
        logger.info(f"  → {artist} - {title}")
        logger.info(f"    └─ Will scrobble at {timestamp_str} (estimated)")

        # Respect max tracks limit
        if len(tracks_to_scrobble) >= max_tracks:
            logger.info(f"  ⏸️  Stopping: Reached max tracks limit ({max_tracks})")
            break

    logger.info("="*60)
    logger.info(f"Result: {len(tracks_to_scrobble)} tracks ready to scrobble (out of {len(today_tracks)} from today)")

    return tracks_to_scrobble


def main():
    """Main scrobbling function with mobile gap-filling and smart detection"""
    mode_str = "DRY RUN MODE" if DRY_RUN else "LIVE MODE"
    logger.info(f"Starting YouTube Music scrobbler with mobile gap-filling ({mode_str})...")

    if DRY_RUN:
        logger.info("⚠️  DRY RUN: No tracks will be actually scrobbled")

    # Connect to Last.fm
    try:
        network = pylast.LastFMNetwork(
            api_key=LASTFM_API_KEY,
            api_secret=LASTFM_API_SECRET,
            username=LASTFM_USERNAME,
            password_hash=pylast.md5(LASTFM_PASSWORD),
        )
        logger.info("Connected to Last.fm successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Last.fm: {e}")
        sys.exit(1)

    # Fetch Last.fm recent scrobbles (for mobile detection)
    lastfm_recent_scrobbles = {}
    if ENABLE_MOBILE_DETECTION:
        lastfm_recent_scrobbles = get_lastfm_recent_scrobbles(network, RECENT_WINDOW_HOURS)
        if not lastfm_recent_scrobbles:
            logger.warning("Mobile detection enabled but no recent Last.fm scrobbles found")
    else:
        logger.info("Mobile detection disabled (will scrobble all tracks from YouTube Music)")

    # Login to YouTube Music
    ytmusic = login_to_ytmusic()
    if not ytmusic:
        logger.error("Failed to login to YouTube Music")
        sys.exit(1)

    # Get listening history
    ytmusic_history = get_listening_history(ytmusic)
    if not ytmusic_history:
        logger.warning("No listening history available")
        return

    # Load comprehensive scrobble history
    scrobble_history = load_scrobble_history()

    # Clean up old history entries (older than 2 weeks) and save cleaned version
    cleaned_history = cleanup_old_history(scrobble_history)
    if len(cleaned_history) != len(scrobble_history):
        save_scrobble_history(cleaned_history)
        logger.info(f"Cleaned up history: {len(scrobble_history)} → {len(cleaned_history)} entries")
    scrobble_history = cleaned_history

    # Extract 'Today' tracks from YouTube Music history
    today_tracks = extract_today_tracks(ytmusic_history)

    if not today_tracks:
        logger.info("No tracks from 'Today' found in YouTube Music history")
        return

    # Process tracks with mobile gap detection
    tracks_to_scrobble = process_today_tracks_with_gap_detection(
        today_tracks,
        lastfm_recent_scrobbles,
        scrobble_history,
        MAX_SCROBBLES_PER_RUN
    )

    if not tracks_to_scrobble:
        logger.info("No new tracks to scrobble (all tracks either on Last.fm or in bot history)")
        return

    # Fix track-timestamp pairing
    # The tracks were processed oldest-to-newest with timestamps calculated backwards from current_time
    # This created wrong pairing: oldest track → newest timestamp (backwards!)
    # Fix: reverse only the tracks list, keep timestamps same, then re-pair
    tracks_only = [track for track, _ in tracks_to_scrobble]
    timestamps_only = [ts for _, ts in tracks_to_scrobble]
    tracks_only.reverse()  # Now: [newest, middle, oldest]
    tracks_to_scrobble = list(zip(tracks_only, timestamps_only))
    logger.info("Fixed timestamp pairing (oldest track → oldest timestamp, newest track → newest timestamp)")

    # Summary before scrobbling
    logger.info("")
    logger.info(f"📊 Summary: Will scrobble {len(tracks_to_scrobble)} tracks")
    if DRY_RUN:
        logger.info("⚠️  DRY RUN: Showing what would be scrobbled (not actually scrobbling)")
    logger.info("")

    # Scrobble tracks with their estimated timestamps
    successful_scrobbles = 0

    for i, (track, timestamp) in enumerate(tracks_to_scrobble):
        track_id = track['videoId']
        artist = safe_get_artist_name(track)
        title = safe_get_title(track)

        timestamp_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would scrobble: {artist} - {title} at {timestamp_str}")
            successful_scrobbles += 1
        else:
            logger.info(f"Scrobbling ({i+1}/{len(tracks_to_scrobble)}): {artist} - {title} at {timestamp_str}")

            if scrobble_track(network, track, timestamp):
                # Add to comprehensive history with the actual timestamp used
                add_to_scrobble_history(track, timestamp, source="ytmusic_bot")
                successful_scrobbles += 1
            else:
                logger.error(f"Failed to scrobble: {artist} - {title}")

            # Small delay between scrobbles to avoid rate limiting
            if i < len(tracks_to_scrobble) - 1:
                time.sleep(2)

    # Summary
    logger.info("")
    if DRY_RUN:
        logger.info(f"✅ DRY RUN completed: {successful_scrobbles} tracks would be scrobbled")
        logger.info(f"   Run without --dry-run to actually scrobble these tracks")
    else:
        if successful_scrobbles > 0:
            logger.info(f"✅ Successfully scrobbled {successful_scrobbles}/{len(tracks_to_scrobble)} tracks")
        else:
            logger.error("❌ No tracks were successfully scrobbled")
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
#!/usr/bin/env python3
"""
Oracle Cloud version of YTMusic Scrobbler
Runs as a periodic script instead of continuous Docker container
"""
import time
import os
import datetime
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
    
    for track_id, track_data in history.items():
        if track_data.get('scrobbled_at', 0) >= cutoff_time:
            cleaned_history[track_id] = track_data
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
    
    # Comprehensive featuring variations
    featuring_patterns = [
        r'\s*\bfeaturing\b\s*',  # Exact word "featuring"
        r'\s*\bfeat\.\s*',       # "feat." with period
        r'\s*\bfeat\b\s*',       # "feat" without period  
        r'\s*\bft\.\s*',         # "ft." with period
        r'\s*\bft\b\s*',         # "ft" without period
        r'\s*\bwith\b\s*',       # "with" as exact word
        r'\s*\bx\b\s*',          # "x" as exact word (common in hip-hop/rap)
        r'\s*\bversus\b\s*',     # "versus" as exact word
        r'\s*\bvs\.\s*',         # "vs." with period
        r'\s*\bvs\b\s*',         # "vs" without period
        r'\s*\band\b\s*',        # "and" as exact word (only in featuring context)
        r'\s*&\s*',              # "&" symbol (common in collaborations)
    ]
    
    # Replace all variations with consistent " ft "
    for pattern in featuring_patterns:
        text = re.sub(pattern, ' ft ', text, flags=re.IGNORECASE)
    
    # Clean up multiple ft occurrences
    text = re.sub(r'\s*ft\s+ft\s*', ' ft ', text)
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def normalize_remix_versions(text: str) -> str:
    """Normalize remix and version information"""
    if not text:
        return ""
    
    # Common remix/version patterns to standardize
    version_patterns = [
        (r'\s*\(Radio Edit\)', ' (Radio Edit)'),
        (r'\s*\(Extended Mix\)', ' (Extended Mix)'),
        (r'\s*\(Club Mix\)', ' (Club Mix)'),
        (r'\s*\(Original Mix\)', ''),  # Remove "Original Mix" as it's redundant
        (r'\s*\(Remix\)', ' (Remix)'),
        (r'\s*\(Remaster\)', ' (Remaster)'),
        (r'\s*\(Remastered\)', ' (Remastered)'),
        (r'\s*\(Deluxe Edition\)', ' (Deluxe Edition)'),
        (r'\s*\(Deluxe Version\)', ' (Deluxe Edition)'),
        (r'\s*\(Acoustic\)', ' (Acoustic)'),
        (r'\s*\(Live\)', ' (Live)'),
        (r'\s*\(Instrumental\)', ' (Instrumental)'),
    ]
    
    for pattern, replacement in version_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
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
                track_artist = normalize_text(track.get_artist().get_name(), is_artist=True)
                track_title = normalize_text(track.get_name(), is_artist=False)
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
            
            artist_name = track.get_artist().get_name()
            track_name = track.get_name()
            logger.info(f"Candidate: {artist_name} - {track_name} (similarity: {similarity_score}, listeners: {popularity})")
            
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
        artist_name = best_track.get_artist().get_name()
        track_name = best_track.get_name()
        popularity = next(pop for t, _, pop in candidates_with_popularity if t == best_track)
        logger.info(f"Selected best match: {artist_name} - {track_name} (weighted score: {best_weighted_score:.1f}, listeners: {popularity})")
    
    return best_track


def scrobble_track(network, track, custom_timestamp: Optional[int] = None) -> bool:
    """Scrobble a single track to Last.fm with enhanced metadata cleanup and fuzzy matching"""
    try:
        # Extract original metadata
        original_artist = track['artists'][0]['name']
        original_title = track['title']
        original_album = track.get('album', {}).get('name', '')
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
            # Use the matched track's details
            matched_artist = best_track.get_artist().get_name()
            matched_title = best_track.get_name()
            
            # Try to get album from the matched track, fallback to cleaned album
            try:
                matched_album = best_track.get_album().get_name() if best_track.get_album() else cleaned_album
            except:
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


def add_to_scrobble_history(track: Dict, timestamp: int) -> None:
    """Add a track to the comprehensive scrobble history"""
    track_id = track['videoId']
    duration_seconds = get_track_duration_seconds(track)
    
    track_data = {
        'artist': track['artists'][0]['name'],
        'title': track['title'],
        'album': track.get('album', {}).get('name', ''),
        'scrobbled_at': timestamp,
        'duration_seconds': duration_seconds,
        'youtube_url': f"https://music.youtube.com/watch?v={track_id}"
    }
    
    # Load existing history
    history = load_scrobble_history()
    
    # Create a unique key for this scrobble (track_id + timestamp)
    scrobble_key = f"{track_id}_{timestamp}"
    
    # Add new track with unique key
    history[scrobble_key] = track_data
    
    # Clean up old entries and save
    cleaned_history = cleanup_old_history(history)
    save_scrobble_history(cleaned_history)


def get_track_scrobble_timestamps(track_id: str, scrobble_history: Dict[str, Dict]) -> List[int]:
    """Get all timestamps when a specific track was scrobbled"""
    timestamps = []
    for scrobble_key, scrobble_data in scrobble_history.items():
        # Extract track_id from scrobble_key (format: track_id_timestamp)
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


def find_tracks_to_scrobble(ytmusic_history: List[Dict], scrobble_history: Dict[str, Dict]) -> List[Tuple[Dict, int]]:
    """Find tracks that need to be scrobbled with their proposed timestamps"""
    tracks_to_scrobble = []
    current_time = int(time.time())
    
    logger.info(f"Checking YouTube Music history for tracks that can be scrobbled...")
    
    # Process tracks in reverse order (oldest first) and assign timestamps
    for i, track in enumerate(reversed(ytmusic_history)):
        track_id = track['videoId']
        artist = track['artists'][0]['name']
        title = track['title']
        
        # Calculate proposed timestamp (spaced 2 minutes apart, working backwards from current time)
        proposed_timestamp = current_time - (len(ytmusic_history) - i - 1) * 120
        
        # Check if this track can be scrobbled at the proposed time
        can_scrobble, reason = can_scrobble_track(track, proposed_timestamp, scrobble_history)
        
        if can_scrobble:
            tracks_to_scrobble.append((track, proposed_timestamp))
            logger.info(f"✅ {artist} - {title}: {reason}")
        else:
            logger.info(f"⏭️  {artist} - {title}: {reason}")
    
    logger.info(f"Found {len(tracks_to_scrobble)} tracks that can be scrobbled")
    return tracks_to_scrobble


def main():
    """Main scrobbling function with comprehensive history tracking"""
    logger.info("Starting YouTube Music scrobbler with comprehensive history tracking...")
    
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
        # Only save if we actually removed entries (avoid unnecessary disk writes)
        save_scrobble_history(cleaned_history)
        logger.info(f"Saved cleaned history with {len(cleaned_history)} entries")
    scrobble_history = cleaned_history
    
    # Find tracks that need to be scrobbled with their proposed timestamps
    tracks_to_scrobble = find_tracks_to_scrobble(ytmusic_history, scrobble_history)
    
    if not tracks_to_scrobble:
        logger.info("No new tracks to scrobble")
        return
    
    # Scrobble tracks with their calculated timestamps
    successful_scrobbles = 0
    most_recent_track_id = None
    
    for i, (track, timestamp) in enumerate(tracks_to_scrobble):
        track_id = track['videoId']
        artist = track['artists'][0]['name']
        title = track['title']
        
        timestamp_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Scrobbling track {i+1}/{len(tracks_to_scrobble)}: {artist} - {title} at {timestamp_str}")
        
        if scrobble_track(network, track, timestamp):
            # Add to comprehensive history with the actual timestamp used
            add_to_scrobble_history(track, timestamp)
            successful_scrobbles += 1
            most_recent_track_id = track_id
        else:
            logger.error(f"Failed to scrobble: {artist} - {title}")
        
        # Small delay between scrobbles to avoid rate limiting
        if i < len(tracks_to_scrobble) - 1:
            time.sleep(2)
    
    # Update legacy history file with most recent track
    if most_recent_track_id:
        save_last_scrobbled(most_recent_track_id)
    
    if successful_scrobbles > 0:
        logger.info(f"Successfully scrobbled {successful_scrobbles}/{len(tracks_to_scrobble)} tracks")
    else:
        logger.error("No tracks were successfully scrobbled")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
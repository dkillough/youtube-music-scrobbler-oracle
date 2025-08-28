#!/usr/bin/env python3
"""
Test suite for enhanced metadata cleanup functionality
"""
import sys
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


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
    
    # Comprehensive featuring variations with word boundaries
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


def clean_track_metadata(artist: str, title: str, album: str = "") -> tuple:
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
    
    return cleaned_artist, cleaned_title, cleaned_album


def test_metadata_cleanup():
    """Comprehensive test suite for metadata cleanup functionality"""
    
    print("🧪 Testing Enhanced Metadata Cleanup Functionality\n")
    
    # Test cases: (original_artist, original_title, expected_artist, expected_title, description)
    test_cases = [
        # YouTube-specific suffixes
        ("Taylor Swift - Topic", "Anti-Hero (Official Music Video)", "Taylor Swift", "Anti-Hero", "YouTube suffixes removal"),
        ("Drake VEVO", "God's Plan", "Drake", "God's Plan", "VEVO suffix removal"),
        ("The Beatles", "Hey Jude [Official Video]", "The Beatles", "Hey Jude", "Bracketed suffix removal"),
        
        # Featuring variations
        ("Post Malone feat. 21 Savage", "rockstar", "Post Malone ft 21 Savage", "rockstar", "feat. normalization"),
        ("The Weeknd featuring Daft Punk", "Starboy", "The Weeknd ft Daft Punk", "Starboy", "featuring normalization"),
        ("Artist x Collaborator", "Song Title", "Artist ft Collaborator", "Song Title", "x normalization"),
        ("Artist & Other Artist", "Song", "Artist ft Other Artist", "Song", "& normalization"),
        
        # Remix/Version handling
        ("DJ Snake", "Taki Taki (Original Mix)", "DJ Snake", "Taki Taki", "Original Mix removal"),
        ("Calvin Harris", "Feel So Close (Radio Edit)", "Calvin Harris", "Feel So Close (Radio Edit)", "Radio Edit preservation"),
        ("Avicii", "Levels (Extended Mix)", "Avicii", "Levels (Extended Mix)", "Extended Mix preservation"),
        ("Artist", "Song (Deluxe Version)", "Artist", "Song (Deluxe Edition)", "Version standardization"),
        
        # Complex cases
        ("Martin Garrix - Topic", "Animals (Official Video) feat. Someone", "Martin Garrix", "Animals ft Someone", "Multiple issues"),
        ("Artist VEVO", "Song (Original Mix) [HD]", "Artist", "Song", "Multiple cleanups"),
        
        # Edge cases
        ("Artist ft. Someone", "Song ft. Other", "Artist ft Someone", "Song ft Other", "Existing ft. normalization"),
        ("", "Empty Artist Test", "", "Empty Artist Test", "Empty artist handling"),
        ("Artist", "", "Artist", "", "Empty title handling"),
    ]
    
    print("=" * 100)
    passed = 0
    failed = 0
    
    for i, (artist, title, expected_artist, expected_title, description) in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}: {description}")
        print(f"Input:    Artist: '{artist}' | Title: '{title}'")
        
        # Test the cleaning function
        result_artist, result_title, _ = clean_track_metadata(artist, title, "")
        
        print(f"Expected: Artist: '{expected_artist}' | Title: '{expected_title}'")
        print(f"Result:   Artist: '{result_artist}' | Title: '{result_title}'")
        
        # Check if results match expectations
        if result_artist == expected_artist and result_title == expected_title:
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
            failed += 1
            if result_artist != expected_artist:
                print(f"   Artist mismatch: got '{result_artist}', expected '{expected_artist}'")
            if result_title != expected_title:
                print(f"   Title mismatch: got '{result_title}', expected '{expected_title}'")
    
    print(f"\n{'='*100}")
    print(f"📊 Test Results: {passed} passed, {failed} failed out of {len(test_cases)} total")
    
    if failed == 0:
        print("🎉 All tests passed! Metadata cleanup is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
    
    return failed == 0


if __name__ == "__main__":
    success = test_metadata_cleanup()
    sys.exit(0 if success else 1)
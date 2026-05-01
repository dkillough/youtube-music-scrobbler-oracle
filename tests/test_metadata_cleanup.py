#!/usr/bin/env python3
"""
Test suite for enhanced metadata cleanup functionality
"""
import sys
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


def clean_youtube_metadata(text: str, is_artist: bool = False, is_album: bool = False) -> str:
    """Clean YouTube Music specific metadata issues"""
    if not text:
        return ""

    text = text.strip()

    # Remove YouTube-specific suffixes (universal — safe for both artist and title)
    youtube_suffixes = [
        r'\s*-\s*Topic$',
        r'\s*VEVO$',
    ]

    for suffix in youtube_suffixes:
        text = re.sub(suffix, '', text, flags=re.IGNORECASE)

    # Artist-only suffixes (not safe for titles — "This Music", "Gold Records" are real titles)
    if is_artist:
        artist_suffixes = [
            r'\s*Records$',
            r'\s*Official$',
        ]
        for suffix in artist_suffixes:
            text = re.sub(suffix, '', text, flags=re.IGNORECASE)

    # Album cleanup: only strip Explicit/Clean markers — preserve meaningful
    # bracketed info like [Deluxe Edition], [Remastered], [Bonus Track Edition].
    if is_album:
        text = re.sub(r'\s*[\[\(](Explicit|Clean)[\]\)]\s*', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

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

    # Featuring variations — only unambiguous patterns
    featuring_patterns = [
        (r'\bfeaturing\b', 'feat.'),  # Exact word "featuring"
        (r'\bfeat\b(?!\.)', 'feat.'),  # "feat" without period (add period)
        (r'\bft\.', 'feat.'),          # "ft." with period
        (r'\bft\b(?!\.)', 'feat.'),    # "ft" without period
        (r'\bversus\b', 'feat.'),      # "versus" as exact word
        (r'\bvs\.', 'feat.'),          # "vs." with period
        (r'\bvs\b(?!\.)', 'feat.'),    # "vs" without period
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


def clean_track_metadata(artist: str, title: str, album: str = "") -> tuple:
    """Clean and normalize track metadata for better matching"""
    # Clean each field
    cleaned_artist = clean_youtube_metadata(artist, is_artist=True)
    cleaned_title = clean_youtube_metadata(title, is_artist=False)
    cleaned_album = clean_youtube_metadata(album, is_album=True)
    
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
        ("Post Malone feat. 21 Savage", "rockstar", "Post Malone feat. 21 Savage", "rockstar", "feat. normalization"),
        ("The Weeknd featuring Daft Punk", "Starboy", "The Weeknd feat. Daft Punk", "Starboy", "featuring normalization"),
        ("Artist x Collaborator", "Song Title", "Artist x Collaborator", "Song Title", "x preserved (ambiguous)"),
        ("Artist & Other Artist", "Song", "Artist & Other Artist", "Song", "& preserved (ambiguous)"),

        # False-positive regression tests — real artists/titles that must NOT be mangled
        ("piri & tommy", "on & on", "piri & tommy", "on & on", "Ampersand in real artist and title"),
        ("underscores", "Music", "underscores", "Music", "Title is literally 'Music'"),
        ("Starjunk 95", "This Music", "Starjunk 95", "This Music", "Title ending in Music"),
        ("Simon and Garfunkel", "The Sound of Silence", "Simon and Garfunkel", "The Sound of Silence", "And in real artist name"),

        # Remix/Version handling
        ("DJ Snake", "Taki Taki (Original Mix)", "DJ Snake", "Taki Taki", "Original Mix removal"),
        ("Calvin Harris", "Feel So Close (Radio Edit)", "Calvin Harris", "Feel So Close (Radio Edit)", "Radio Edit preservation"),
        ("Avicii", "Levels (Extended Mix)", "Avicii", "Levels (Extended Mix)", "Extended Mix preservation"),
        ("Artist", "Song (Deluxe Version)", "Artist", "Song (Deluxe Version)", "Deluxe Version preservation"),

        # Complex cases
        ("Martin Garrix - Topic", "Animals (Official Video) feat. Someone", "Martin Garrix", "Animals feat. Someone", "Multiple issues"),
        ("Artist VEVO", "Song (Original Mix) [HD]", "Artist", "Song", "Multiple cleanups"),

        # Square bracket removal
        ("The Beatles", "Let It Be [Remastered 2009]", "The Beatles", "Let It Be", "Remaster bracket removal"),
        ("Queen", "Bohemian Rhapsody [Live at Wembley]", "Queen", "Bohemian Rhapsody", "Live performance bracket removal"),
        ("Pink Floyd", "Comfortably Numb [2011 Remaster]", "Pink Floyd", "Comfortably Numb", "Year remaster bracket removal"),
        ("Artist", "Song [Radio Edit] feat. Someone", "Artist", "Song feat. Someone", "Bracket with featuring"),
        ("Artist", "Song [Explicit] [Remastered]", "Artist", "Song", "Multiple brackets removal"),
        ("Artist", "Song [Audio]", "Artist", "Song", "Audio bracket removal"),

        # Edge cases
        ("Artist ft. Someone", "Song ft. Other", "Artist feat. Someone", "Song feat. Other", "Existing ft. normalization"),
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
    
    # Album-specific tests: Explicit/Clean markers are stripped, other
    # bracketed info (Deluxe Edition, Remastered, etc.) is preserved.
    album_test_cases = [
        ("Future Nostalgia [Explicit]", "Future Nostalgia", "Bracketed Explicit removal"),
        ("Future Nostalgia [Clean]", "Future Nostalgia", "Bracketed Clean removal"),
        ("Album (Explicit)", "Album", "Parenthesized Explicit removal"),
        ("Album (Clean)", "Album", "Parenthesized Clean removal"),
        ("Album [explicit]", "Album", "Case-insensitive Explicit removal"),
        ("Renaissance [Deluxe Edition]", "Renaissance [Deluxe Edition]", "Deluxe Edition preserved"),
        ("Abbey Road [Remastered]", "Abbey Road [Remastered]", "Remastered preserved"),
        ("Album [Explicit] [Deluxe Edition]", "Album [Deluxe Edition]", "Strip Explicit, keep Deluxe"),
        ("", "", "Empty album handling"),
    ]

    for i, (album, expected_album, description) in enumerate(album_test_cases, 1):
        print(f"\n🔍 Album Test {i}: {description}")
        print(f"Input:    Album: '{album}'")

        _, _, result_album = clean_track_metadata("Artist", "Title", album)

        print(f"Expected: Album: '{expected_album}'")
        print(f"Result:   Album: '{result_album}'")

        if result_album == expected_album:
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
            failed += 1
            print(f"   Album mismatch: got '{result_album}', expected '{expected_album}'")

    total = len(test_cases) + len(album_test_cases)
    print(f"\n{'='*100}")
    print(f"📊 Test Results: {passed} passed, {failed} failed out of {total} total")

    if failed == 0:
        print("🎉 All tests passed! Metadata cleanup is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")

    return failed == 0


if __name__ == "__main__":
    success = test_metadata_cleanup()
    sys.exit(0 if success else 1)
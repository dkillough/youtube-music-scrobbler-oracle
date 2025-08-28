#!/usr/bin/env python3
"""
Test suite for duration-based duplicate prevention logic
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


def get_track_duration_seconds(track_dict: dict) -> int:
    """Simulate track duration extraction (simplified version)"""
    try:
        # Try to get duration from the track data
        duration_text = track_dict.get('duration', '')
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
        duration_seconds = track_dict.get('duration_seconds')
        if duration_seconds:
            return int(duration_seconds)
        
        # Default fallback: assume 3.5 minutes for unknown duration
        return 210
        
    except Exception:
        return 210


def can_scrobble_track(track: dict, proposed_timestamp: int, previous_scrobbles: list) -> tuple:
    """Test if a track can be scrobbled at the proposed timestamp"""
    track_duration = get_track_duration_seconds(track)
    min_gap_required = track_duration + 30  # Track length + 30 seconds buffer
    
    if not previous_scrobbles:
        return True, "No previous scrobbles found"
    
    # Check if proposed timestamp has sufficient gap from any previous scrobble
    for prev_timestamp in previous_scrobbles:
        time_gap = abs(proposed_timestamp - prev_timestamp)
        if time_gap < min_gap_required:
            gap_minutes = time_gap // 60
            required_minutes = min_gap_required // 60
            return False, f"Too close to previous scrobble ({gap_minutes}m gap, need {required_minutes}m)"
    
    return True, f"Sufficient gap from {len(previous_scrobbles)} previous scrobbles"


def test_duration_logic():
    """Test the duration-based duplicate prevention logic"""
    
    print("🕒 Testing Duration-Based Duplicate Prevention Logic\n")
    
    # Test cases
    test_cases = [
        {
            "description": "Short song - first play",
            "track": {"duration": "2:30", "title": "Short Song"},
            "proposed_time": 1000,
            "previous_scrobbles": [],
            "should_allow": True,
        },
        {
            "description": "Short song - too soon replay (1 minute gap)",
            "track": {"duration": "2:30", "title": "Short Song"},
            "proposed_time": 1060,  # 1 minute later
            "previous_scrobbles": [1000],
            "should_allow": False,
        },
        {
            "description": "Short song - sufficient gap (4 minutes)",
            "track": {"duration": "2:30", "title": "Short Song"},
            "proposed_time": 1240,  # 4 minutes later
            "previous_scrobbles": [1000],
            "should_allow": True,
        },
        {
            "description": "Long song - insufficient gap (5 minutes)",
            "track": {"duration": "7:45", "title": "Long Song"},
            "proposed_time": 1300,  # 5 minutes later
            "previous_scrobbles": [1000],
            "should_allow": False,
        },
        {
            "description": "Long song - sufficient gap (9 minutes)",
            "track": {"duration": "7:45", "title": "Long Song"},
            "proposed_time": 1540,  # 9 minutes later
            "previous_scrobbles": [1000],
            "should_allow": True,
        },
        {
            "description": "Multiple previous scrobbles - valid gap from all",
            "track": {"duration": "3:30", "title": "Popular Song"},
            "proposed_time": 2000,
            "previous_scrobbles": [1000, 1500],  # 16.7 and 8.3 minutes ago
            "should_allow": True,
        },
        {
            "description": "Multiple previous scrobbles - too close to one",
            "track": {"duration": "3:30", "title": "Popular Song"},
            "proposed_time": 1700,
            "previous_scrobbles": [1000, 1500],  # 11.7 and 3.3 minutes ago (too close to second)
            "should_allow": False,
        },
        {
            "description": "Unknown duration fallback (3.5 minutes assumed)",
            "track": {"title": "Unknown Duration Song"},
            "proposed_time": 1300,  # 5 minutes later (should be enough for 3.5+0.5 = 4 min requirement)
            "previous_scrobbles": [1000],
            "should_allow": True,
        },
        {
            "description": "Hour-long podcast episode",
            "track": {"duration": "1:15:30", "title": "Long Podcast"},
            "proposed_time": 5000,
            "previous_scrobbles": [1000],  # 66.7 minutes ago
            "should_allow": False,  # Need 75.5 minutes
        },
        {
            "description": "Hour-long podcast - sufficient gap",
            "track": {"duration": "1:15:30", "title": "Long Podcast"},
            "proposed_time": 5560,  # 76 minutes later (75.5*60 + 30 seconds = 4560 seconds needed)
            "previous_scrobbles": [1000],
            "should_allow": True,
        }
    ]
    
    print("=" * 80)
    passed = 0
    failed = 0
    
    for i, case in enumerate(test_cases, 1):
        track = case["track"]
        proposed_time = case["proposed_time"]
        previous_scrobbles = case["previous_scrobbles"]
        should_allow = case["should_allow"]
        description = case["description"]
        
        print(f"\n🔍 Test Case {i}: {description}")
        
        # Get track duration for context
        duration_seconds = get_track_duration_seconds(track)
        duration_str = f"{duration_seconds//60}:{duration_seconds%60:02d}"
        print(f"Track: '{track['title']}' ({duration_str})")
        print(f"Required gap: {(duration_seconds + 30)//60}:{(duration_seconds + 30)%60:02d}")
        
        if previous_scrobbles:
            gaps = [f"{abs(proposed_time - prev)//60}m" for prev in previous_scrobbles]
            print(f"Previous scrobbles: {len(previous_scrobbles)} (gaps: {', '.join(gaps)})")
        else:
            print("Previous scrobbles: None")
        
        # Test the logic
        can_scrobble, reason = can_scrobble_track(track, proposed_time, previous_scrobbles)
        
        print(f"Result: {'✅ ALLOW' if can_scrobble else '❌ BLOCK'} - {reason}")
        
        # Check if result matches expectation
        if can_scrobble == should_allow:
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
            expected = "should allow" if should_allow else "should block"
            actual = "allowed" if can_scrobble else "blocked"
            print(f"   Expected to {expected}, but {actual}")
            failed += 1
    
    print(f"\n{'='*80}")
    print(f"📊 Test Results: {passed} passed, {failed} failed out of {len(test_cases)} total")
    
    if failed == 0:
        print("🎉 All tests passed! Duration logic is working correctly.")
        print("\n✨ Key features validated:")
        print("- Prevents duplicate scrobbles within track duration + 30s")
        print("- Supports songs from seconds to hours in length")
        print("- Handles multiple previous scrobbles correctly")
        print("- Graceful fallback for unknown durations")
        print("- Perfect for loop/repeat listening patterns")
    else:
        print("⚠️  Some tests failed. Please review the duration logic implementation.")
    
    return failed == 0


if __name__ == "__main__":
    success = test_duration_logic()
    sys.exit(0 if success else 1)
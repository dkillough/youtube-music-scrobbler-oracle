# YTMusic Scrobbler - Test Suite

This directory contains comprehensive test suites for the YTMusic Scrobbler Oracle Cloud edition.

## Test Files

### `test_metadata_cleanup.py`
Tests the enhanced metadata cleanup functionality including:
- YouTube-specific suffix removal (`- Topic`, `VEVO`, etc.)
- Title cleanup (`(Official Video)`, `[HD]`, etc.)
- Featuring artist normalization (`feat.`, `featuring`, `x` → `ft`)
- Remix/version standardization
- Edge cases and error handling

**Run with:** `python3 test_metadata_cleanup.py`

### `test_integration.py`
Tests the integration between metadata cleanup and fuzzy matching:
- End-to-end processing pipeline
- Search query normalization
- Candidate matching simulation
- Score calculation validation
- Fallback mechanism testing

**Run with:** `python3 test_integration.py`

### `test_duration_logic.py`
Tests the duration-based duplicate prevention system:
- Track duration parsing (MM:SS, HH:MM:SS formats)
- Minimum gap calculations (duration + 30s buffer)
- Multiple previous scrobbles handling
- Various track lengths (seconds to hours)
- Edge cases and fallback logic

**Run with:** `python3 test_duration_logic.py`

## Running All Tests

```bash
# Run individual tests
cd tests/
python3 test_metadata_cleanup.py
python3 test_integration.py
python3 test_duration_logic.py

# Or run all tests
for test in test_*.py; do python3 "$test"; done
```

## Test Coverage

### Metadata Cleanup
✅ YouTube suffixes (`- Topic`, `VEVO`, `Records`)  
✅ Video/audio indicators (`(Official Video)`, `[HD]`)  
✅ Featuring variations (`feat.`, `featuring`, `x`, `&`)  
✅ Version standardization (`(Original Mix)` → removed)  
✅ Complex combinations  
✅ Edge cases (empty strings, etc.)

### Integration Testing
✅ Cleanup → Search pipeline  
✅ Fuzzy matching accuracy  
✅ Score calculation  
✅ Fallback mechanisms  
✅ Real-world scenarios

### Duration Logic
✅ Duration parsing (multiple formats)  
✅ Gap calculation accuracy  
✅ Multiple scrobble tracking  
✅ Various track lengths  
✅ Default fallback handling  
✅ Realistic listening patterns

## Expected Output

All tests should pass with detailed output showing:
- Test case descriptions
- Input/output comparisons
- Pass/fail status for each test
- Summary statistics
- Feature validation confirmations

If any tests fail, review the implementation in the main scrobbler files.

## Dependencies

These tests use only Python standard library modules and don't require external dependencies. They simulate the behavior of external libraries (like fuzzywuzzy) for testing purposes.
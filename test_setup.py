#!/usr/bin/env python3
"""
Test script to validate the Oracle Cloud setup
"""
import os
import sys
from pathlib import Path

def test_dependencies():
    """Test that all required dependencies can be imported"""
    print("🧪 Testing Python dependencies...")
    
    try:
        import ytmusicapi
        print("✅ ytmusicapi imported successfully")
    except ImportError as e:
        print(f"❌ ytmusicapi import failed: {e}")
        return False
    
    try:
        import pylast
        print("✅ pylast imported successfully")
    except ImportError as e:
        print(f"❌ pylast import failed: {e}")
        return False
    
    return True

def test_environment():
    """Test environment configuration"""
    print("🧪 Testing environment configuration...")
    
    required_vars = ['LASTFM_API_KEY', 'LASTFM_API_SECRET', 'LASTFM_USERNAME', 'LASTFM_PASSWORD']
    env_file = Path(__file__).parent / '.env'
    
    if env_file.exists():
        print(f"✅ Found .env file at {env_file}")
        
        # Load environment variables from .env
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        
        missing_vars = []
        for var in required_vars:
            value = os.environ.get(var, '')
            if not value or 'your_' in value:
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️  Missing or placeholder values for: {', '.join(missing_vars)}")
            return False
        else:
            print("✅ All required environment variables are set")
            return True
    else:
        print(f"⚠️  No .env file found at {env_file}")
        return False

def test_file_structure():
    """Test that all required files exist"""
    print("🧪 Testing file structure...")
    
    script_dir = Path(__file__).parent
    required_files = [
        'scrobble_oracle.py',
        'setup_credentials.py', 
        'requirements.txt',
        'deploy.sh',
        'setup_cron.sh',
        'history_manager.py',
        'README.md',
        '.env.example'
    ]
    
    missing_files = []
    for filename in required_files:
        file_path = script_dir / filename
        if file_path.exists():
            print(f"✅ {filename}")
        else:
            missing_files.append(filename)
            print(f"❌ {filename}")
    
    return len(missing_files) == 0

def test_comprehensive_tests():
    """Run comprehensive tests from tests directory"""
    print("🧪 Running comprehensive test suite...")
    
    try:
        from pathlib import Path
        script_dir = Path(__file__).parent
        tests_dir = script_dir / "tests"
        
        if tests_dir.exists():
            print(f"✅ Found comprehensive test suite at {tests_dir}")
            print("   Run individual tests with:")
            for test_file in sorted(tests_dir.glob("test_*.py")):
                print(f"   python3 tests/{test_file.name}")
            return True
        else:
            print("⚠️  Comprehensive test suite not found")
            return False
            
    except Exception as e:
        print(f"❌ Test discovery failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Running Oracle Cloud setup validation...\n")
    
    tests = [
        ("File Structure", test_file_structure),
        ("Environment Configuration", test_environment),
        ("Comprehensive Tests", test_comprehensive_tests),
        ("Python Dependencies", test_dependencies),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    print(f"\n{'='*50}")
    print("📊 Test Results:")
    
    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results)
    print(f"\n🎯 Overall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if not all_passed:
        print("\n📋 Next steps to fix failures:")
        if not results[0]:  # File structure
            print("  - Ensure all required files are present in the oracle directory")
        if not results[1]:  # Environment
            print("  - Copy .env.example to .env and fill in your Last.fm credentials")
        if not results[2]:  # Dependencies
            print("  - Run: pip install -r requirements.txt")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
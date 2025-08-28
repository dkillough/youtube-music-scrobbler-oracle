#!/usr/bin/env python3
"""
Setup script for YouTube Music credentials on Oracle Cloud
This script helps you configure the browser.json file needed for YouTube Music API access
"""
import os
import sys
from pathlib import Path
import ytmusicapi

SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)

BROWSER_CONFIG = CONFIG_DIR / "browser.json"

def print_instructions():
    """Print instructions for getting YouTube Music headers"""
    print("\n" + "="*60)
    print("YouTube Music Cookie Setup Instructions")
    print("="*60)
    print()
    print("1. Open a new browser tab")
    print("2. Open Developer Tools (F12 or Ctrl+Shift+I)")
    print("3. Go to the 'Network' tab in Developer Tools")
    print("4. Navigate to https://music.youtube.com")
    print("5. Make sure you're logged in to your YouTube Music account")
    print("6. In the Network tab, filter by '/browse' in the search bar")
    print("7. If you don't see any requests, scroll down or click on Library")
    print("8. Find a POST request to a URL containing '/browse'")
    print("9. Right-click on the request:")
    print("   - Firefox: Copy Value → Copy Request Headers")
    print("   - Chrome: Copy → Copy Request Headers")
    print("10. Paste the headers below when prompted")
    print()
    print("="*60)
    print()

def setup_credentials():
    """Interactive setup for YouTube Music credentials"""
    print("Setting up YouTube Music credentials for Oracle Cloud...")
    
    if BROWSER_CONFIG.exists():
        response = input(f"Config file already exists at {BROWSER_CONFIG}. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return False
    
    print_instructions()
    
    print("Please paste your request headers here:")
    print("(Paste all headers, then press Enter on an empty line to finish)")
    
    headers_lines = []
    while True:
        try:
            line = input()
            if line.strip() == "":
                break
            headers_lines.append(line)
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            return False
    
    if not headers_lines:
        print("No headers provided. Setup cancelled.")
        return False
    
    headers_raw = "\n".join(headers_lines)
    
    try:
        print("Creating YouTube Music configuration...")
        ytmusicapi.setup(filepath=str(BROWSER_CONFIG), headers_raw=headers_raw)
        print(f"✅ Configuration saved to {BROWSER_CONFIG}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating configuration: {e}")
        return False

def verify_credentials():
    """Verify that the credentials work"""
    try:
        from ytmusicapi import YTMusic
        print("Verifying credentials...")
        ytmusic = YTMusic(str(BROWSER_CONFIG))
        history = ytmusic.get_history()
        if history:
            print(f"✅ Credentials verified! Found {len(history)} tracks in history.")
            if history:
                latest_track = history[0]
                print(f"Latest track: {latest_track['artists'][0]['name']} - {latest_track['title']}")
            return True
        else:
            print("⚠️  Credentials work but no listening history found.")
            return True
            
    except Exception as e:
        print(f"❌ Credential verification failed: {e}")
        return False

def main():
    """Main setup function"""
    print("YouTube Music Scrobbler - Oracle Cloud Setup")
    print(f"Config directory: {CONFIG_DIR}")
    
    if setup_credentials():
        if verify_credentials():
            print("\n✅ Setup completed successfully!")
            print(f"You can now run the scrobbler with: python3 {SCRIPT_DIR / 'scrobble_oracle.py'}")
            return True
    
    print("\n❌ Setup failed. Please try again.")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
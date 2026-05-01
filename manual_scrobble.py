#!/usr/bin/env python3
"""Manually scrobble a curated track list to Last.fm using project credentials.

Usage:
    python3 manual_scrobble.py <csv_file> [--dry-run] [--env <path>] [--spacing <seconds>]

CSV format: header row "artist,track" then one row per track in oldest-to-newest play order.
The last track is scrobbled at "now"; earlier tracks are spaced backwards by --spacing (default 240s).
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import pylast

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("csv_file", type=Path, help="CSV with columns: artist, track")
parser.add_argument("--env", type=Path, default=Path("/opt/ytmusic-scrobbler/.env"),
                    help="Path to .env file with LASTFM_* credentials")
parser.add_argument("--spacing", type=int, default=240,
                    help="Seconds between scrobble timestamps (default: 240)")
parser.add_argument("--dry-run", action="store_true",
                    help="Print what would be scrobbled without submitting")
args = parser.parse_args()

ENV_FILE = args.env
CSV_FILE = args.csv_file
SPACING_SECONDS = args.spacing
DRY_RUN = args.dry_run

env = {}
with open(ENV_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v

network = pylast.LastFMNetwork(
    api_key=env["LASTFM_API_KEY"],
    api_secret=env["LASTFM_API_SECRET"],
    username=env["LASTFM_USERNAME"],
    password_hash=pylast.md5(env["LASTFM_PASSWORD"]),
)
print(f"Connected as {env['LASTFM_USERNAME']}")

with open(CSV_FILE, "r") as f:
    reader = csv.DictReader(f)
    tracks = [(row["artist"], row["track"]) for row in reader]

print(f"Loaded {len(tracks)} tracks from CSV")

now = int(time.time())
last_ts = now - 30
oldest_ts = last_ts - (len(tracks) - 1) * SPACING_SECONDS

print(f"Last scrobble timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_ts))}")
print(f"First scrobble timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(oldest_ts))}")
print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
print()

scrobbles = []
for i, (artist, title) in enumerate(tracks):
    ts = oldest_ts + i * SPACING_SECONDS
    scrobbles.append({"artist": artist, "title": title, "timestamp": ts})
    print(f"{i+1:3d}. [{time.strftime('%H:%M:%S', time.localtime(ts))}] {artist} — {title}")

if DRY_RUN:
    print("\nDRY RUN: not submitting.")
    sys.exit(0)

print("\nSubmitting in batches of 50...")
for i in range(0, len(scrobbles), 50):
    batch = scrobbles[i:i+50]
    network.scrobble_many(batch)
    print(f"  Submitted {len(batch)} scrobbles ({i+1}–{i+len(batch)})")
    if i + 50 < len(scrobbles):
        time.sleep(1)

print(f"\nDone. {len(scrobbles)} tracks scrobbled to {env['LASTFM_USERNAME']}.")

#!/usr/bin/env python3
"""Create browser.json from a Chrome "Copy as cURL" command.

Chrome has no "Copy Request Headers" menu item (that is Firefox-only), so this
accepts what Chrome does offer: right-click the /browse request in the Network
tab -> Copy -> Copy as cURL, then paste it here.

Usage:
    python3 setup_from_curl.py [--config-dir DIR] [curl_file]

With no file argument the cURL command is read from stdin: paste it, then press
Ctrl-D on a blank line.
"""
import argparse
import re
import sys
from pathlib import Path

import ytmusicapi

# ytmusicapi's setup_browser() refuses to write unless both of these are present,
# and YTMusic() only selects browser auth when authorization holds a SAPISIDHASH.
REQUIRED = ("cookie", "x-goog-authuser", "authorization")

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("curl_file", nargs="?", type=Path,
                    help="File containing the cURL command (default: read stdin)")
parser.add_argument("--config-dir", type=Path,
                    default=Path(__file__).parent / "config",
                    help="Config directory to write browser.json into")
args = parser.parse_args()

if args.curl_file:
    raw = args.curl_file.read_text()
else:
    print("Paste the 'Copy as cURL' command, then press Ctrl-D on a blank line:\n",
          file=sys.stderr)
    raw = sys.stdin.read()

if not raw.strip():
    sys.exit("No input received.")

# Pull the flag values out with a regex rather than a full shell parse. Copied
# commands arrive with continuations flattened or newlines stripped, and the
# --data-raw JSON payload defeats shlex entirely, but the quoting around each
# -H/-b value survives intact.
SENTINEL = "\x00"
# Chrome escapes an embedded single quote as the shell idiom '\'' - park it.
raw = raw.replace("'\\''", SENTINEL)
# Join shell line-continuations: bash uses trailing "\", Windows cmd uses "^".
raw = re.sub(r"[\\^]\s*\n", " ", raw)

FLAG_VALUE = (
    r"(?:{flags})\s+"          # the flag itself
    r"(?:'([^']*)'"            # single-quoted value
    r'|"((?:[^"\\]|\\.)*)"'    # or double-quoted, honouring backslash escapes
    r"|(\S+))"                 # or bare
)


def flag_values(flags):
    pattern = FLAG_VALUE.format(flags=flags)
    for match in re.finditer(pattern, raw):
        value = next(g for g in match.groups() if g is not None)
        yield value.replace(SENTINEL, "'")


headers = {}
for value in flag_values(r"-H|--header"):
    name, sep, header_value = value.partition(":")
    if sep:
        headers[name.strip().lower()] = header_value.strip()

# Chrome sometimes emits the cookie via -b rather than -H 'cookie: ...'
for value in flag_values(r"-b|--cookie"):
    headers["cookie"] = value.strip()

if not headers:
    sys.exit("No headers found. Make sure you copied 'Copy as cURL', not 'Copy as fetch'.")

# A single signed-in Google account often means Chrome omits x-goog-authuser,
# but ytmusicapi requires it. Account 0 is the correct default in that case.
if "x-goog-authuser" not in headers:
    headers["x-goog-authuser"] = "0"
    print("note: x-goog-authuser was absent; defaulting to 0", file=sys.stderr)

missing = [h for h in REQUIRED if h not in headers]
if missing:
    sys.exit(
        f"Missing required header(s): {', '.join(missing)}\n"
        "Copy a POST request to /youtubei/v1/browse while logged in to "
        "music.youtube.com - static asset requests carry no auth."
    )

if "SAPISIDHASH" not in headers["authorization"]:
    sys.exit("The authorization header has no SAPISIDHASH; copy a /browse request instead.")

if "__Secure-3PAPISID" not in headers["cookie"]:
    sys.exit("The cookie is missing __Secure-3PAPISID; make sure you are logged in.")

args.config_dir.mkdir(parents=True, exist_ok=True)
target = args.config_dir / "browser.json"

headers_raw = "\n".join(f"{name}: {value}" for name, value in headers.items())
ytmusicapi.setup(filepath=str(target), headers_raw=headers_raw)
print(f"Wrote {target} ({len(headers)} headers)")

from ytmusicapi import YTMusic  # noqa: E402  (import after the file exists)

try:
    history = YTMusic(str(target)).get_history()
except Exception as e:
    target.unlink(missing_ok=True)
    sys.exit(f"Verification failed, {target.name} removed: {type(e).__name__}: {e}")

print(f"Verified: retrieved {len(history)} tracks.")
if history:
    top = history[0]
    artist = top["artists"][0]["name"] if top.get("artists") else "?"
    print(f"Most recent play: {artist} - {top['title']}")

"""
config.py
---------
Central configuration for Synoptic: Weather Intelligence and Response Platform.

Everything in this project runs on the Python standard library only.
Nothing here needs `pip install` and nothing here needs a database server,
a BI tool license, or an API key.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "synoptic.db")
DASHBOARD_PATH = os.path.join(OUTPUT_DIR, "dashboard.html")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# NWS (National Weather Service) API
# api.weather.gov is free, public, and requires no API key -- only a
# descriptive User-Agent header, per NWS API policy.
# ---------------------------------------------------------------------------
NWS_BASE_URL = "https://api.weather.gov"
NWS_ALERTS_ENDPOINT = f"{NWS_BASE_URL}/alerts/active"
NWS_USER_AGENT = "SynopticWeatherPlatform (contact: your-email@example.com)"

# Limit the alert pull to specific states to keep runtime/data volume
# reasonable for a local demo. Empty list = all active US alerts.
NWS_STATES = ["TX", "FL", "CA", "OK", "LA", "NY"]

# ---------------------------------------------------------------------------
# Mastodon (social sentiment source)
# Public hashtag timelines on Mastodon are readable with no auth token,
# e.g. https://mastodon.social/api/v1/timelines/tag/weather
# ---------------------------------------------------------------------------
MASTODON_INSTANCE = "https://mastodon.social"
MASTODON_HASHTAGS = ["weather", "flooding", "tornado", "hurricane", "storm"]
MASTODON_LIMIT = 40  # posts per hashtag, per Mastodon API max-ish

# ---------------------------------------------------------------------------
# HTTP behavior
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Live server (real-time dashboard)
# ---------------------------------------------------------------------------
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765
REFRESH_INTERVAL_SECONDS = 90  # how often the background thread re-polls NWS/Mastodon
STATIC_DIR = os.path.join(BASE_DIR, "static")
US_STATES_GEOJSON_PATH = os.path.join(DATA_DIR, "us_states.geojson")

# ---------------------------------------------------------------------------
# Outage simulation tuning
# ---------------------------------------------------------------------------
SEVERITY_WEIGHTS = {
    "Extreme": 1.0,
    "Severe": 0.75,
    "Moderate": 0.45,
    "Minor": 0.2,
    "Unknown": 0.1,
}

# Fraction of an affected area's population assumed to lose power at
# maximum simulated severity (i.e. Extreme severity, worst-case keywords).
MAX_OUTAGE_PENETRATION = 0.35

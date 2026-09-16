"""
us_states_meta.py
------------------
Static name <-> USPS abbreviation lookup for the 50 states + DC.
Used to cross-reference NWS alert `area_desc` text (which uses state
abbreviations, e.g. "Travis, TX") against the bundled GeoJSON (which uses
full names, e.g. "Texas"), and to resolve a location search box entry.
"""

STATE_ABBR_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
STATE_NAME_TO_ABBR = {v: k for k, v in STATE_ABBR_TO_NAME.items()}

# A handful of well-known cities for the location search box, so a
# non-technical user can type "Austin" instead of a state code.
KNOWN_LOCATIONS = [
    ("Austin, TX", "TX", 30.2672, -97.7431),
    ("Houston, TX", "TX", 29.7604, -95.3698),
    ("Dallas, TX", "TX", 32.7767, -96.7970),
    ("San Antonio, TX", "TX", 29.4241, -98.4936),
    ("Miami, FL", "FL", 25.7617, -80.1918),
    ("Orlando, FL", "FL", 28.5383, -81.3792),
    ("Tampa, FL", "FL", 27.9506, -82.4572),
    ("Los Angeles, CA", "CA", 34.0522, -118.2437),
    ("San Francisco, CA", "CA", 37.7749, -122.4194),
    ("Sacramento, CA", "CA", 38.5816, -121.4944),
    ("Oklahoma City, OK", "OK", 35.4676, -97.5164),
    ("New Orleans, LA", "LA", 29.9511, -90.0715),
    ("New York, NY", "NY", 40.7128, -74.0060),
    ("Chicago, IL", "IL", 41.8781, -87.6298),
    ("Atlanta, GA", "GA", 33.7490, -84.3880),
    ("Phoenix, AZ", "AZ", 33.4484, -112.0740),
    ("Denver, CO", "CO", 39.7392, -104.9903),
    ("Seattle, WA", "WA", 47.6062, -122.3321),
    ("Boston, MA", "MA", 42.3601, -71.0589),
    ("Nashville, TN", "TN", 36.1627, -86.7816),
]

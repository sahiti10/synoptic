"""
population.py
--------------
Small, self-contained reference tables used for population-level impact
analysis, so the pipeline doesn't need a live census API call or a GIS
population raster.

STATE_POPULATION: 2023 Census estimates (rounded), keyed by USPS code.
CITIES: a sample of major US cities with lon/lat, used as "population
    anchor points" -- if a weather alert polygon contains or is near one
    of these points, that city's population is counted as impacted.
"""

STATE_POPULATION = {
    "AL": 5108468, "AK": 733406, "AZ": 7431344, "AR": 3067732, "CA": 38965193,
    "CO": 5877610, "CT": 3617176, "DE": 1031890, "FL": 22610726, "GA": 11029227,
    "HI": 1435138, "ID": 1964726, "IL": 12549689, "IN": 6862199, "IA": 3200517,
    "KS": 2940546, "KY": 4526154, "LA": 4573749, "ME": 1395722, "MD": 6180253,
    "MA": 7001399, "MI": 10037261, "MN": 5737915, "MS": 2939690, "MO": 6196010,
    "MT": 1122069, "NE": 1978379, "NV": 3194176, "NH": 1402054, "NJ": 9290841,
    "NM": 2113344, "NY": 19571216, "NC": 10835491, "ND": 783926, "OH": 11785935,
    "OK": 4053824, "OR": 4233358, "PA": 12961683, "RI": 1095962, "SC": 5373555,
    "SD": 909824, "TN": 7126489, "TX": 30503301, "UT": 3417734, "VT": 647464,
    "VA": 8715698, "WA": 7812880, "WV": 1770071, "WI": 5910955, "WY": 584057,
    "DC": 678972, "PR": 3205691,
}

# (name, state, lon, lat, population) -- major-metro sample, deliberately
# small so the demo runs fast; extend freely.
CITIES = [
    ("Houston", "TX", -95.3698, 29.7604, 2302878),
    ("Dallas", "TX", -96.7970, 32.7767, 1304379),
    ("Austin", "TX", -97.7431, 30.2672, 974447),
    ("San Antonio", "TX", -98.4936, 29.4241, 1495295),
    ("Miami", "FL", -80.1918, 25.7617, 449514),
    ("Tampa", "FL", -82.4572, 27.9506, 398173),
    ("Orlando", "FL", -81.3792, 28.5383, 307573),
    ("Jacksonville", "FL", -81.6557, 30.3322, 971319),
    ("Los Angeles", "CA", -118.2437, 34.0522, 3898747),
    ("San Francisco", "CA", -122.4194, 37.7749, 873965),
    ("Sacramento", "CA", -121.4944, 38.5816, 524943),
    ("San Diego", "CA", -117.1611, 32.7157, 1386932),
    ("Oklahoma City", "OK", -97.5164, 35.4676, 681054),
    ("Tulsa", "OK", -95.9928, 36.1540, 411894),
    ("New Orleans", "LA", -90.0715, 29.9511, 383997),
    ("Baton Rouge", "LA", -91.1871, 30.4515, 227470),
    ("New York City", "NY", -74.0060, 40.7128, 8335897),
    ("Buffalo", "NY", -78.8784, 42.8864, 278349),
    ("Albany", "NY", -73.7562, 42.6526, 99224),
]


def population_for_state(state_code: str) -> int:
    return STATE_POPULATION.get(state_code, 0)


def cities_in_states(state_codes):
    if not state_codes:
        return CITIES
    codes = set(state_codes)
    return [c for c in CITIES if c[1] in codes]

# 🌪️ Synoptic — Weather Intelligence and Response Platform

A real-time ETL pipeline and live dashboard that ingests live NWS weather
alerts and public Mastodon posts, stores them for spatial querying, runs
population-level impact analysis and outage-risk simulation, and shows all
of it on an interactive map that auto-refreshes.

**Zero-install by design:** everything runs on the Python standard library.
No `pip install`, no database server, no BI tool license, no API keys, no
frontend build step. Clone it, run one command, done.

## Two ways to run it

| | Command | What you get |
|---|---|---|
| **Live dashboard** (recommended) | `python main.py --serve` | A real-time local web app at `http://127.0.0.1:8765` — auto-refreshing map, live alert feed, browser notifications, installable as an app |
| **Static snapshot** | `python main.py` | A single `output/dashboard.html` file, generated once, good for sharing or archiving a point-in-time view |

---

## The live dashboard

```bash
python main.py --serve
```

This starts a small local server (Python's `http.server`, no Flask/FastAPI
needed) that:

- fetches active NWS alerts + Mastodon posts once at startup, then again
  every 90 seconds in the background (`config.REFRESH_INTERVAL_SECONDS`),
  so the page never goes stale without you doing anything;
- serves a JSON API (`/api/alerts`, `/api/status`, `/api/states-geojson`,
  `/api/locations`) that the page polls to update itself live, without a
  full reload;
- serves the frontend itself — one HTML page, one CSS file, one JS file,
  no build tools, no npm.

### What the UI is built for

The design brief was: *simplified, and useful to a non-technical person who
just wants to know if their area is affected* — not a data-analyst tool.

- **A status band up top** answers the one question people actually have —
  "is my area OK?" — in plain language (All Clear / Advisory / Watch /
  Warning), not a raw severity code.
- **Search by city, or tap 📍 to use your current location** — no state
  codes or county names required.
- **Click any alert in the list (or any state on the map) and the map
  zooms and pans to that region**, with a popup showing what it is, when it
  was issued, and the simulated outage risk.
- **Filter chips** are generated from whatever hazard types are actually
  active right now (Tornado, Flood, Winter, Wind, …) — no chip for a hazard
  with zero current alerts.
- **A live badge** ("Updated 12s ago") and a manual refresh button make the
  auto-refresh visible and trustworthy instead of invisible/magic.
- **New Severe/Extreme alerts trigger a toast**, and — if the person opts
  in via "Enable alert notifications" — a real OS-level browser
  notification, even if the tab isn't focused.
- **Installable as an app**: a `manifest.json` + minimal service worker
  mean the browser will offer "Install app" / "Add to Home Screen", so
  repeat visits are one tap instead of retyping a URL. (This is what
  actually drives "downloads" for a tool like this — a real PWA install
  prompt, not a marketing gimmick.)
- **Accessible by default**: semantic landmarks, a skip link, visible
  keyboard focus, `aria-live` regions for the status/live badge, color is
  never the only signal (severity also has text labels and icons), and
  `prefers-reduced-motion` disables the map's pan/zoom animation.
- **Dark by default, with a real light theme** via `prefers-color-scheme`
  — deliberately chosen because this app is realistically opened at night,
  outdoors, or on a phone with adaptive brightness during an actual storm.

### CLI options (also apply to `--serve`)

```bash
python main.py --serve --states TX FL CA     # limit to specific states
python main.py --serve --hashtags storm flooding
python main.py --serve --no-open             # don't auto-launch a browser
```

Open `http://127.0.0.1:8765` if it doesn't launch automatically. Stop the
server with `Ctrl+C`.

---

## Why it looks different from a typical "Python + Pandas + GeoPandas +
PostgreSQL/PostGIS + Power BI" stack

This project reimplements that original architecture with the Python
standard library only, so anyone can clone the repo and run it locally
with no setup step:

| Original design                  | This implementation                         | Why |
|-----------------------------------|----------------------------------------------|-----|
| PostgreSQL + PostGIS               | `sqlite3` + GeoJSON columns                  | No server/daemon to install or run; ships with Python |
| GeoPandas / Shapely                | `src/spatial_utils.py` (haversine, ray-casting point-in-polygon, centroid) | No compiled GIS deps to `pip install` |
| `requests`                         | `urllib.request`                             | Stdlib HTTP client |
| Pandas                             | plain `dict`/`list` + `sqlite3.Row`          | Avoids a large binary dependency for a demo-scale dataset |
| Power BI + DAX                     | Generated single-file HTML dashboard (inline SVG charts, no CDN) | Power BI is Windows-only, licensed software; this opens in any browser, offline |

The logic — spatial joins, severity weighting, sentiment scoring, outage
simulation — is the same *idea* as the original project; only the runtime
dependencies changed.

If you *do* have Pandas/GeoPandas/PostgreSQL/Power BI available and want to
swap them back in, the modules are cleanly separated (`src/db.py`,
`src/spatial_utils.py`, `src/dashboard.py`) specifically so any one of them
can be swapped without touching the rest of the pipeline.

---

## Architecture

```
                 ┌───────────────────┐       ┌──────────────────────┐
                 │  NWS Alerts API   │       │  Mastodon public tag  │
                 │  api.weather.gov  │       │  timelines            │
                 └─────────┬─────────┘       └───────────┬──────────┘
                           │  urllib.request                │  urllib.request
                           ▼                                ▼
                 ┌──────────────────────────────────────────────────┐
                 │                 src/etl_pipeline.py               │
                 │  extract → sentiment scoring → spatial impact     │
                 │  analysis → outage-risk simulation → load         │
                 └───────────────────────┬────────────────────────┘
                                          ▼
                             ┌────────────────────────┐
                             │   data/synoptic.db      │
                             │   (SQLite + GeoJSON)     │
                             └──────┬──────────────┬────┘
                                    ▼              ▼
                     ┌──────────────────┐   ┌──────────────────────────┐
                     │ src/dashboard.py  │   │ src/server.py             │
                     │ → static snapshot │   │ background refresh loop  │
                     │ output/dashboard  │   │ + JSON API + static app  │
                     │ .html             │   │ (static/index.html,      │
                     └──────────────────┘   │  style.css, app.js)      │
                                              │ → http://127.0.0.1:8765 │
                                              └──────────────────────────┘
```

## Project layout

```
synoptic/
├── main.py                    # CLI entry point (`--serve` for live mode)
├── config.py                  # all settings in one place
├── requirements.txt           # documents the "no dependencies" design
├── src/
│   ├── nws_client.py          # NWS active-alerts API client (urllib)
│   ├── mastodon_client.py     # Mastodon public hashtag timeline client (urllib)
│   ├── sentiment.py           # lexicon-based sentiment scoring
│   ├── spatial_utils.py       # haversine, point-in-polygon, centroid (pure math)
│   ├── population.py          # static state/city population reference data
│   ├── us_states_meta.py      # state name/abbreviation lookup + known cities
│   ├── outage_simulation.py   # population impact + outage-risk heuristic
│   ├── db.py                  # SQLite schema + CRUD helpers
│   ├── etl_pipeline.py        # orchestrates extract → transform → load
│   ├── dashboard.py           # generates the static HTML snapshot
│   └── server.py              # real-time HTTP server + background refresh + JSON API
├── static/                    # the live dashboard's frontend (served by server.py)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── manifest.json          # makes the app installable (PWA)
│   ├── sw.js                  # service worker: caches the app shell
│   └── icon.svg
├── data/
│   ├── us_states.geojson      # bundled US state boundaries (offline map, no CDN)
│   └── synoptic.db            # created at runtime (gitignored)
├── scripts/
│   └── seed_demo_data.py      # loads synthetic data, no internet required
├── tests/
│   ├── test_spatial.py        # offline unit tests
│   ├── test_sentiment.py      # offline unit tests
│   ├── test_server.py         # offline unit tests for the live-server logic
│   └── test_pipeline_offline.py  # end-to-end test with synthetic data
└── output/                    # dashboard.html lives here (gitignored)
```

## Requirements

- Python 3.8 or newer. That's it.
- An internet connection *only if* you want to pull live data from NWS/Mastodon.
  Everything else, including previewing the dashboard, works fully offline.

## Quickstart

```bash
git clone https://github.com/<your-username>/synoptic.git
cd synoptic

# Option A: the live, auto-refreshing dashboard (recommended)
python main.py --serve

# Option B: a one-time static HTML snapshot
python main.py

# Option C: no internet? preview instantly with synthetic demo data
python scripts/seed_demo_data.py
# then open output/dashboard.html in your browser
```

### CLI options

```bash
python main.py --states TX FL CA          # limit NWS alerts to specific states
python main.py --hashtags storm flooding  # limit Mastodon hashtags
python main.py --etl-only                 # just refresh the database
python main.py --dashboard-only           # just rebuild the HTML from existing data
python main.py --no-open                  # don't auto-launch a browser
```

### Running tests

```bash
python -m unittest discover -s tests -v
```

All tests run offline (no network calls) — they exercise the spatial math,
sentiment scoring, and a full DB → impact analysis → outage simulation →
dashboard build using synthetic alert/post data.

## What each pipeline stage does

1. **Extract** — `src/nws_client.py` pulls active alerts (GeoJSON) from
   `api.weather.gov`; `src/mastodon_client.py` pulls recent public posts for
   configured hashtags from a Mastodon instance's public tag timeline.
2. **Transform**
   - `src/sentiment.py` scores each post positive/neutral/negative using a
     small hand-built lexicon (no NLP package required).
   - `src/spatial_utils.py` computes each alert polygon's centroid and
     tests reference cities for polygon containment (`point_in_multipolygon`)
     using a ray-casting algorithm, or distance-based proximity
     (`haversine_km`) when an alert has no polygon.
   - `src/outage_simulation.py` turns severity + keyword signals from the
     alert text + affected population into a 0–1 risk score and a simulated
     count of customers without power.
3. **Load** — `src/db.py` upserts everything into SQLite tables:
   `alerts`, `social_posts`, `impact_analysis`, `outage_simulation`.
4. **Visualize** — `src/dashboard.py` queries SQLite and renders a single
   HTML file with KPI cards, severity/sentiment bar charts, an alert
   location map, and ranked tables — all inline SVG, no external chart
   library.

## Data sources

- **NWS Alerts API** — free, public, no key: <https://www.weather.gov/documentation/services-web-api>
- **Mastodon public tag timelines** — free, public, no key: <https://docs.joinmastodon.org/methods/timelines/#tag>
- **Population figures** — static 2023 Census-based estimates embedded in `src/population.py`, so no external census API call is needed.

## Notes on the outage simulation

`simulate_outage()` is a transparent heuristic, not a utility-grade
predictive model: `risk_score = severity_weight + keyword_bonus + urgency_bonus`,
capped at 1.0, multiplied by affected population and a configurable max
penetration rate (`MAX_OUTAGE_PENETRATION` in `config.py`). It exists to
demonstrate the full pipeline end-to-end with a believable, explainable
output — swap in a real model if you have one.

## License

MIT — do whatever you'd like with it.

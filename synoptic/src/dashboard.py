"""
dashboard.py
------------
Generates a single, self-contained HTML file that plays the role Power BI
played in the original design: a live-feeling dashboard over the SQLite
data, with charts for alert severity, social sentiment, and simulated
outage risk, plus a simple map of alert locations.

No external JS/CSS libraries, no CDN calls, no internet connection needed
to VIEW it (only to regenerate the data via the ETL step). All charts are
plain inline SVG built by Python string templates -- so `open output/dashboard.html`
in any browser just works, offline, on any machine.
"""

import html
import json

from config import DASHBOARD_PATH
from src import db, spatial_utils

SEVERITY_COLORS = {
    "Extreme": "#b91c1c",
    "Severe": "#ea580c",
    "Moderate": "#d97706",
    "Minor": "#65a30d",
    "Unknown": "#6b7280",
}
SENTIMENT_COLORS = {"positive": "#16a34a", "neutral": "#6b7280", "negative": "#dc2626"}

# Continental US-ish bounding box used to project alert points onto the map SVG.
MAP_LON_RANGE = (-125.0, -66.0)
MAP_LAT_RANGE = (24.0, 49.5)
MAP_W, MAP_H = 720, 420


def _project(lon, lat):
    lon0, lon1 = MAP_LON_RANGE
    lat0, lat1 = MAP_LAT_RANGE
    x = (lon - lon0) / (lon1 - lon0) * MAP_W
    y = (1 - (lat - lat0) / (lat1 - lat0)) * MAP_H
    return x, y


def _bar_chart_svg(labels_counts, colors, width=560, bar_h=28, gap=14, max_label_w=140):
    if not labels_counts:
        return "<p class='muted'>No data yet.</p>"
    max_count = max(c for _, c in labels_counts) or 1
    chart_w = width - max_label_w - 60
    rows = []
    y = 10
    for label, count in labels_counts:
        bar_len = (count / max_count) * chart_w
        color = colors.get(label, "#3b82f6")
        rows.append(f"""
        <text x="0" y="{y + bar_h * 0.65}" class="bar-label">{html.escape(str(label))}</text>
        <rect x="{max_label_w}" y="{y}" width="{bar_len:.1f}" height="{bar_h}" rx="4" fill="{color}"></rect>
        <text x="{max_label_w + bar_len + 8}" y="{y + bar_h * 0.65}" class="bar-value">{count}</text>
        """)
        y += bar_h + gap
    total_h = y
    return f'<svg viewBox="0 0 {width} {total_h}" width="100%" height="{total_h}">{"".join(rows)}</svg>'


def _map_svg(points):
    """points: list of (lon, lat, severity, label)"""
    markers = []
    for lon, lat, severity, label in points:
        x, y = _project(lon, lat)
        if not (0 <= x <= MAP_W and 0 <= y <= MAP_H):
            continue
        color = SEVERITY_COLORS.get(severity, "#3b82f6")
        markers.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" fill-opacity="0.85" '
            f'stroke="#111827" stroke-width="0.5"><title>{html.escape(label)}</title></circle>'
        )
    frame = (f'<rect x="0" y="0" width="{MAP_W}" height="{MAP_H}" rx="10" '
             f'fill="#0f172a" fill-opacity="0.04" stroke="#cbd5e1"/>')
    return (f'<svg viewBox="0 0 {MAP_W} {MAP_H}" width="100%" height="auto" '
            f'style="max-height:420px">{frame}{"".join(markers)}</svg>')


def _rows_to_table(rows, columns):
    thead = "".join(f"<th>{html.escape(c[1])}</th>" for c in columns)
    body_rows = []
    for r in rows:
        cells = "".join(f"<td>{html.escape(str(r.get(c[0], '')))}</td>" for c in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def build_dashboard():
    db.init_db()  # safe no-op if tables already exist; prevents a crash on a
                   # fresh clone where --dashboard-only is run before any ETL
    with db.get_connection() as conn:
        alerts = db.fetch_all(conn, "SELECT * FROM alerts ORDER BY sent DESC")
        posts = db.fetch_all(conn, "SELECT * FROM social_posts ORDER BY created_at DESC")
        outages = db.fetch_all(
            conn,
            "SELECT * FROM outage_simulation ORDER BY simulated_customers_out DESC LIMIT 15",
        )
        impact_totals = db.fetch_all(
            conn,
            """SELECT city, state, SUM(population_affected) AS pop
               FROM impact_analysis GROUP BY city, state
               ORDER BY pop DESC LIMIT 10""",
        )

    # ---- KPIs ----
    total_alerts = len(alerts)
    severe_extreme = sum(1 for a in alerts if a["severity"] in ("Severe", "Extreme"))
    total_posts = len(posts)
    total_customers_out = sum(o["simulated_customers_out"] or 0 for o in outages)

    # ---- Severity breakdown ----
    severity_counts = {}
    for a in alerts:
        severity_counts[a["severity"] or "Unknown"] = severity_counts.get(a["severity"] or "Unknown", 0) + 1
    severity_order = ["Extreme", "Severe", "Moderate", "Minor", "Unknown"]
    severity_pairs = [(s, severity_counts.get(s, 0)) for s in severity_order if severity_counts.get(s, 0) > 0]

    # ---- Sentiment breakdown ----
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for p in posts:
        label = p.get("sentiment_label") or "neutral"
        sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
    sentiment_pairs = [(k, v) for k, v in sentiment_counts.items() if v > 0]

    # ---- Map points ----
    map_points = []
    for a in alerts:
        geom = db.geometry_from_row(a)
        if geom:
            try:
                lon, lat = spatial_utils.geometry_centroid(geom)
                map_points.append((lon, lat, a["severity"], f"{a['event']} ({a['severity']}) — {a['area_desc']}"))
            except Exception:
                continue

    severity_bars_svg = _bar_chart_svg(severity_pairs, SEVERITY_COLORS)
    sentiment_bars_svg = _bar_chart_svg(sentiment_pairs, SENTIMENT_COLORS, max_label_w=100)
    map_svg = _map_svg(map_points)

    outage_table = _rows_to_table(
        outages,
        [("event", "Event"), ("severity", "Severity"),
         ("total_population_affected", "Population Affected"),
         ("risk_score", "Risk Score"), ("simulated_customers_out", "Simulated Customers Out")],
    )
    impact_table = _rows_to_table(
        impact_totals,
        [("city", "City"), ("state", "State"), ("pop", "Population Affected")],
    )
    posts_preview = _rows_to_table(
        posts[:12],
        [("hashtag", "Hashtag"), ("author", "Author"),
         ("sentiment_label", "Sentiment"), ("created_at", "Posted")],
    )

    generated_at = alerts[0]["fetched_at"] if alerts else (posts[0]["fetched_at"] if posts else "n/a")

    html_out = HTML_TEMPLATE.format(
        generated_at=html.escape(str(generated_at)),
        total_alerts=total_alerts,
        severe_extreme=severe_extreme,
        total_posts=total_posts,
        total_customers_out=f"{total_customers_out:,}",
        severity_bars_svg=severity_bars_svg,
        sentiment_bars_svg=sentiment_bars_svg,
        map_svg=map_svg,
        outage_table=outage_table,
        impact_table=impact_table,
        posts_preview=posts_preview,
        raw_json=html.escape(json.dumps({
            "alerts": total_alerts, "posts": total_posts,
            "severity": severity_counts, "sentiment": sentiment_counts,
        })),
    )

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    return DASHBOARD_PATH


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Synoptic — Weather Intelligence &amp; Response Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: #f8fafc; --card: #ffffff; --text: #0f172a; --muted: #64748b;
    --accent: #2563eb; --border: #e2e8f0;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0b1220; --card:#101827; --text:#e5e7eb; --muted:#94a3b8; --border:#1f2937; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); margin: 0 0 28px; font-size: 0.92rem; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; }}
  .kpi .value {{ font-size: 1.8rem; font-weight: 700; }}
  .kpi .label {{ color: var(--muted); font-size: 0.82rem; margin-top: 4px; }}
  .grid {{ display: grid; grid-template-columns: 1.1fr 1fr; gap: 20px; margin-bottom: 20px; }}
  @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; overflow-x: auto; }}
  .card h2 {{ font-size: 1.05rem; margin: 0 0 14px; }}
  .bar-label {{ font-size: 12px; fill: var(--text); }}
  .bar-value {{ font-size: 12px; fill: var(--muted); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .03em; }}
  .muted {{ color: var(--muted); }}
  footer {{ color: var(--muted); font-size: 0.78rem; margin-top: 28px; }}
  .legend {{ display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; font-size:0.78rem; color:var(--muted);}}
  .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; vertical-align:middle;}}
</style>
</head>
<body>
  <h1>🌪️ Synoptic — Weather Intelligence &amp; Response Dashboard</h1>
  <p class="subtitle">Live view over local SQLite data · last ETL run: {generated_at} · fully offline, no external services required to view</p>

  <div class="kpis">
    <div class="kpi"><div class="value">{total_alerts}</div><div class="label">Active NWS Alerts</div></div>
    <div class="kpi"><div class="value">{severe_extreme}</div><div class="label">Severe / Extreme Alerts</div></div>
    <div class="kpi"><div class="value">{total_posts}</div><div class="label">Social Posts Analyzed</div></div>
    <div class="kpi"><div class="value">{total_customers_out}</div><div class="label">Simulated Customers Without Power</div></div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Alerts by Severity</h2>
      {severity_bars_svg}
    </div>
    <div class="card">
      <h2>Social Sentiment (Mastodon)</h2>
      {sentiment_bars_svg}
    </div>
  </div>

  <div class="card" style="margin-bottom:20px;">
    <h2>Alert Locations</h2>
    {map_svg}
    <div class="legend">
      <span><span class="dot" style="background:#b91c1c"></span>Extreme</span>
      <span><span class="dot" style="background:#ea580c"></span>Severe</span>
      <span><span class="dot" style="background:#d97706"></span>Moderate</span>
      <span><span class="dot" style="background:#65a30d"></span>Minor</span>
      <span><span class="dot" style="background:#6b7280"></span>Unknown</span>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Top Simulated Outage Risk</h2>
      {outage_table}
    </div>
    <div class="card">
      <h2>Population Impact by City</h2>
      {impact_table}
    </div>
  </div>

  <div class="card" style="margin-top:20px;">
    <h2>Recent Social Posts</h2>
    {posts_preview}
  </div>

  <footer>
    Generated by Synoptic (pure Python standard library — sqlite3, urllib, math).
    Data: National Weather Service (api.weather.gov) &amp; public Mastodon hashtag timelines.
    Raw summary JSON: <code>{raw_json}</code>
  </footer>
</body>
</html>
"""

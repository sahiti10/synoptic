"""
db.py
-----
Storage layer for Synoptic, built on `sqlite3` (Python standard library).

The original design used PostgreSQL + PostGIS. SQLite ships with every
standard Python install and needs no server process, no credentials, and
no `pip install`, so it's the right substitute for a "clone and run"
project. Geometry is stored as GeoJSON text and interpreted in Python via
`spatial_utils`, instead of native PostGIS geometry columns.
"""

import json
import sqlite3
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    event TEXT,
    severity TEXT,
    certainty TEXT,
    urgency TEXT,
    area_desc TEXT,
    headline TEXT,
    description TEXT,
    sent TEXT,
    effective TEXT,
    expires TEXT,
    geometry_json TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS social_posts (
    id TEXT PRIMARY KEY,
    hashtag TEXT,
    author TEXT,
    content TEXT,
    created_at TEXT,
    url TEXT,
    sentiment_label TEXT,
    sentiment_score INTEGER,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS impact_analysis (
    alert_id TEXT,
    city TEXT,
    state TEXT,
    distance_km REAL,
    inside_polygon INTEGER,
    population_affected INTEGER,
    PRIMARY KEY (alert_id, city)
);

CREATE TABLE IF NOT EXISTS outage_simulation (
    alert_id TEXT PRIMARY KEY,
    event TEXT,
    severity TEXT,
    total_population_affected INTEGER,
    risk_score REAL,
    simulated_customers_out INTEGER,
    generated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_posts_hashtag ON social_posts(hashtag);
CREATE INDEX IF NOT EXISTS idx_impact_alert ON impact_analysis(alert_id);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def upsert_alert(conn, alert: dict):
    conn.execute(
        """
        INSERT INTO alerts (id, event, severity, certainty, urgency, area_desc,
                             headline, description, sent, effective, expires,
                             geometry_json, fetched_at)
        VALUES (:id, :event, :severity, :certainty, :urgency, :area_desc,
                :headline, :description, :sent, :effective, :expires,
                :geometry_json, :fetched_at)
        ON CONFLICT(id) DO UPDATE SET
            event=excluded.event, severity=excluded.severity,
            certainty=excluded.certainty, urgency=excluded.urgency,
            area_desc=excluded.area_desc, headline=excluded.headline,
            description=excluded.description, sent=excluded.sent,
            effective=excluded.effective, expires=excluded.expires,
            geometry_json=excluded.geometry_json, fetched_at=excluded.fetched_at
        """,
        alert,
    )


def upsert_post(conn, post: dict):
    conn.execute(
        """
        INSERT INTO social_posts (id, hashtag, author, content, created_at,
                                   url, sentiment_label, sentiment_score, fetched_at)
        VALUES (:id, :hashtag, :author, :content, :created_at,
                :url, :sentiment_label, :sentiment_score, :fetched_at)
        ON CONFLICT(id) DO UPDATE SET
            hashtag=excluded.hashtag, content=excluded.content,
            sentiment_label=excluded.sentiment_label,
            sentiment_score=excluded.sentiment_score, fetched_at=excluded.fetched_at
        """,
        post,
    )


def insert_impact(conn, row: dict):
    conn.execute(
        """
        INSERT INTO impact_analysis (alert_id, city, state, distance_km,
                                      inside_polygon, population_affected)
        VALUES (:alert_id, :city, :state, :distance_km, :inside_polygon,
                :population_affected)
        ON CONFLICT(alert_id, city) DO UPDATE SET
            distance_km=excluded.distance_km,
            inside_polygon=excluded.inside_polygon,
            population_affected=excluded.population_affected
        """,
        row,
    )


def upsert_outage(conn, row: dict):
    conn.execute(
        """
        INSERT INTO outage_simulation (alert_id, event, severity,
                                        total_population_affected, risk_score,
                                        simulated_customers_out, generated_at)
        VALUES (:alert_id, :event, :severity, :total_population_affected,
                :risk_score, :simulated_customers_out, :generated_at)
        ON CONFLICT(alert_id) DO UPDATE SET
            event=excluded.event, severity=excluded.severity,
            total_population_affected=excluded.total_population_affected,
            risk_score=excluded.risk_score,
            simulated_customers_out=excluded.simulated_customers_out,
            generated_at=excluded.generated_at
        """,
        row,
    )


def fetch_all(conn, query, params=()):
    cur = conn.execute(query, params)
    return [dict(r) for r in cur.fetchall()]


def geometry_from_row(row: dict):
    raw = row.get("geometry_json")
    return json.loads(raw) if raw else None

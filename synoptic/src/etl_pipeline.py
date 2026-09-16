"""
etl_pipeline.py
----------------
Orchestrates the full Extract -> Transform -> Load flow:

  EXTRACT   NWS active alerts (nws_client) + Mastodon public posts (mastodon_client)
  TRANSFORM sentiment scoring (sentiment) + spatial/population impact (outage_simulation)
  LOAD      SQLite (db)

Run directly with `python -m src.etl_pipeline` or via main.py.
"""

import datetime as dt

from src import db, nws_client, mastodon_client, sentiment, outage_simulation
from config import NWS_STATES, MASTODON_HASHTAGS


def _now_iso():
    return dt.datetime.utcnow().isoformat() + "Z"


def run(states=None, hashtags=None, verbose=True):
    states = states if states is not None else NWS_STATES
    hashtags = hashtags if hashtags is not None else MASTODON_HASHTAGS

    db.init_db()
    fetched_at = _now_iso()

    # ---------------- EXTRACT + LOAD: weather alerts ----------------
    if verbose:
        print(f"[ETL] Fetching NWS active alerts for states={states or 'ALL'} ...")
    alerts = nws_client.fetch_active_alerts(states)
    if verbose:
        print(f"[ETL] Retrieved {len(alerts)} alerts.")

    with db.get_connection() as conn:
        for alert in alerts:
            alert["fetched_at"] = fetched_at
            db.upsert_alert(conn, alert)

    # ---------------- EXTRACT + TRANSFORM + LOAD: social posts ------
    if verbose:
        print(f"[ETL] Fetching Mastodon posts for hashtags={hashtags} ...")
    posts = mastodon_client.fetch_all_hashtags(hashtags)
    if verbose:
        print(f"[ETL] Retrieved {len(posts)} social posts.")

    with db.get_connection() as conn:
        for post in posts:
            label, score = sentiment.score_text(post["content"])
            post["sentiment_label"] = label
            post["sentiment_score"] = score
            post["fetched_at"] = fetched_at
            db.upsert_post(conn, post)

    # ---------------- TRANSFORM + LOAD: impact & outage sim ---------
    if verbose:
        print("[ETL] Running spatial impact analysis + outage simulation ...")
    with db.get_connection() as conn:
        for alert in alerts:
            impacted = outage_simulation.impact_for_alert(alert, candidate_states=states)
            for row in impacted:
                db.insert_impact(conn, {"alert_id": alert["id"], **row})

            outage_row = outage_simulation.simulate_outage(alert, impacted)
            outage_row["generated_at"] = fetched_at
            db.upsert_outage(conn, outage_row)

    if verbose:
        print("[ETL] Done. Data loaded into", db.DB_PATH if hasattr(db, "DB_PATH") else "synoptic.db")

    return {"alerts": len(alerts), "posts": len(posts)}


if __name__ == "__main__":
    run()

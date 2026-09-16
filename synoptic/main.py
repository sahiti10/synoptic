#!/usr/bin/env python3
"""
Synoptic — Weather Intelligence and Response Platform
=======================================================
Single entry point. Uses only the Python standard library.

Usage:
    python main.py                 # run ETL, then build + open the dashboard
    python main.py --etl-only      # just fetch data and load the database
    python main.py --dashboard-only  # just rebuild the dashboard from existing data
    python main.py --states TX FL CA
    python main.py --hashtags weather storm flooding
    python main.py --no-open       # don't auto-open the dashboard in a browser
"""

import argparse
import sys
import webbrowser

from src import etl_pipeline, dashboard


def parse_args():
    p = argparse.ArgumentParser(description="Synoptic weather intelligence pipeline")
    p.add_argument("--serve", action="store_true",
                    help="Launch the real-time live dashboard (auto-refreshing server + map)")
    p.add_argument("--etl-only", action="store_true", help="Only run the ETL step")
    p.add_argument("--dashboard-only", action="store_true", help="Only rebuild the static dashboard")
    p.add_argument("--states", nargs="*", default=None, help="USPS state codes to pull NWS alerts for")
    p.add_argument("--hashtags", nargs="*", default=None, help="Mastodon hashtags to pull")
    p.add_argument("--no-open", action="store_true", help="Don't open the dashboard in a browser")
    return p.parse_args()


def main():
    args = parse_args()

    if args.serve:
        from src import server
        server.run(states=args.states, hashtags=args.hashtags, open_browser=not args.no_open)
        return

    if not args.dashboard_only:
        print("=" * 60)
        print("STEP 1/2: Extract-Transform-Load (NWS + Mastodon -> SQLite)")
        print("=" * 60)
        try:
            stats = etl_pipeline.run(states=args.states, hashtags=args.hashtags)
            print(f"[main] ETL complete: {stats['alerts']} alerts, {stats['posts']} posts loaded.\n")
        except Exception as e:
            print(f"[main] ETL failed ({e}). Continuing to build dashboard from any existing data.\n",
                  file=sys.stderr)

    if not args.etl_only:
        print("=" * 60)
        print("STEP 2/2: Building local dashboard (pure HTML/SVG, no libraries)")
        print("=" * 60)
        try:
            path = dashboard.build_dashboard()
            print(f"[main] Dashboard written to: {path}")
            if not args.no_open:
                webbrowser.open(f"file://{path}")
        except Exception as e:
            print(f"[main] Dashboard build failed: {e}", file=sys.stderr)
            print("[main] Try running `python scripts/seed_demo_data.py` for an offline demo, "
                  "or check your internet connection and re-run `python main.py`.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

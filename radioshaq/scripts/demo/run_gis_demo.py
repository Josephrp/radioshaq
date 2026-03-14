#!/usr/bin/env python3
"""GIS demo: set location, get location, operators-nearby, propagation.

Uses POST /gis/location, GET /gis/location/{callsign}, GET /gis/operators-nearby,
GET /radio/propagation. Requires HQ with Postgres/PostGIS for location and
operators-nearby; propagation works without DB. Exits 0 if steps return 2xx (or 503 for DB down).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_utils import (
    API_TIMEOUT,
    expect_status,
    get_gis_location,
    get_gis_operators_nearby,
    get_radio_propagation,
    get_token,
    post_gis_location,
)

# Demo coordinates: SF area (origin), LA area (destination) for propagation
DEMO_LAT_1, DEMO_LON_1 = 37.7749, -122.4194   # SF
DEMO_LAT_2, DEMO_LON_2 = 34.0522, -118.2437  # LA
DEMO_RADIUS_M = 100_000  # 100 km


def main() -> int:
    ap = argparse.ArgumentParser(description="GIS location and propagation demo.")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--callsigns", nargs="+", default=["FLABC-1", "F1XYZ-1"], help="Callsigns to set location for")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print("GIS location and propagation demo")
    print("---------------------------------")
    print(f"Base URL: {base}")
    print(f"Callsigns: {args.callsigns}")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    # 1) Store location for each callsign (may 503 if DB unavailable)
    for i, callsign in enumerate(args.callsigns):
        lat = DEMO_LAT_1 + (i * 0.01)
        lon = DEMO_LON_1 + (i * 0.01)
        r = post_gis_location(base, token, callsign, lat, lon, timeout=API_TIMEOUT)
        if r.status_code == 503:
            print(f"[warn] POST /gis/location {callsign}: 503 (DB unavailable)")
            continue
        if not expect_status(r, 200, f"POST /gis/location {callsign}"):
            return 2
        try:
            print(" ", r.json())
        except Exception:
            pass

    # 2) Get location for first callsign
    first = args.callsigns[0] if args.callsigns else "FLABC-1"
    r = get_gis_location(base, token, first, timeout=API_TIMEOUT)
    if r.status_code == 503:
        print(f"[warn] GET /gis/location/{first}: 503 (DB unavailable)")
    elif r.status_code == 404:
        print(f"[warn] GET /gis/location/{first}: 404 (no location stored)")
    else:
        if not expect_status(r, 200, f"GET /gis/location/{first}"):
            return 3
        try:
            print(" ", r.json())
        except Exception:
            pass

    # 3) Operators nearby (center = SF)
    r = get_gis_operators_nearby(
        base, token, DEMO_LAT_1, DEMO_LON_1,
        radius_meters=DEMO_RADIUS_M,
        recent_hours=24,
        max_results=50,
        timeout=API_TIMEOUT,
    )
    if r.status_code == 503:
        print("[warn] GET /gis/operators-nearby: 503 (DB unavailable)")
    else:
        if not expect_status(r, 200, "GET /gis/operators-nearby"):
            return 4
        try:
            data = r.json()
            print(f"  count={data.get('count', 0)}, radius_m={data.get('radius_meters')}")
        except Exception:
            pass

    # 4) Propagation (no DB required)
    r = get_radio_propagation(
        base, token,
        DEMO_LAT_1, DEMO_LON_1,
        DEMO_LAT_2, DEMO_LON_2,
        timeout=API_TIMEOUT,
    )
    if not expect_status(r, 200, "GET /radio/propagation"):
        return 5
    try:
        data = r.json()
        print(" ", json.dumps(data, indent=2))
    except Exception:
        print(r.text[:300])

    print("\nSummary: GIS location (post/get), operators-nearby, propagation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

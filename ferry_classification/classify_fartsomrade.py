"""
Classify Norwegian ferry routes by fartsområde (1-5) per Sjøfartsdirektoratet.

Fartsområde definitions (Forskrift om fartsområder):
  1 – Helt innelukket farvann (completely enclosed waters)
  2 – Beskyttet farvann (protected from open-sea waves/wind)
  3 – Innaskjærs, åpne strekninger ≤ 5 nm
  4 – Innaskjærs, åpne strekninger ≤ 25 nm
  5 – Liten kystfart (within 20 nm of baseline)

Method:
  Primary: Fetch-based geometric analysis using Natural Earth 10m coastline.
    For each route point, shoots rays in 72 directions and measures the maximum
    unobstructed over-water distance (fetch). Classification uses the route's
    worst-point median fetch and exposure percentage.

  Fallback: When the coastline polygon is too coarse to resolve narrow waterways
    (fetch=0 for all sample points), the route is marked as "ukjent" (unknown).

Data sources:
  - Natural Earth 10m land polygons (auto-downloaded to data/)
  - kart.sdir.no WMS layers 40-43, 94 (fartsområde boundary reference)
"""

import json
import math
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required. Install with: pip install numpy")
    sys.exit(1)

try:
    from shapely.geometry import Point, box, shape
    from shapely.ops import unary_union
except ImportError:
    print("ERROR: shapely is required. Install with: pip install shapely>=2.0")
    sys.exit(1)

try:
    import fiona
except ImportError:
    print("ERROR: fiona is required. Install with: pip install fiona")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SAMBAND_FILE = BASE_DIR / "samband_data.json"

NE_LAND_DIR = DATA_DIR / "ne_10m_land"
NE_LAND_SHP = NE_LAND_DIR / "ne_10m_land.shp"
NE_LAND_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip"

# Fetch analysis parameters
NUM_RAYS = 72          # Directions to shoot rays
MAX_FETCH_NM = 60.0    # Maximum fetch distance (nautical miles)
RAY_STEP_DEG = 0.002   # Ray step size (~220m)

# Classification thresholds
# median_fetch: the median over-water distance across all ray directions
# exposure_pct: fraction of rays reaching > 5nm
THRESHOLDS = {
    1: {"median_max": 1.5, "exposure_max": 0.15},
    2: {"median_max": 3.0, "exposure_max": 0.30},
    3: {"median_max": 5.0, "exposure_max": 0.50},
    4: {"median_max": 15.0, "exposure_max": 0.75},
    # 5: everything else within coastal waters
}


# ── Data loading ───────────────────────────────────────────────────────

def ensure_coastline_data():
    """Download Natural Earth 10m land polygons if not present."""
    if NE_LAND_SHP.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / "ne_10m_land.zip"

    print(f"  Downloading Natural Earth 10m land data...")
    urllib.request.urlretrieve(NE_LAND_URL, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(NE_LAND_DIR)

    zip_path.unlink()
    print(f"  Saved to {NE_LAND_DIR}")


def load_land_polygon():
    """Load and clip Natural Earth land polygon to Norway area."""
    norway_bbox = box(3.0, 57.0, 32.0, 72.0)
    land_geoms = []

    with fiona.open(str(NE_LAND_SHP)) as src:
        for feat in src:
            geom = shape(feat["geometry"])
            if geom.intersects(norway_bbox):
                clipped = geom.intersection(norway_bbox)
                if not clipped.is_empty:
                    land_geoms.append(clipped)

    return unary_union(land_geoms)


# ── Fetch analysis ─────────────────────────────────────────────────────

def compute_fetch_stats(lat, lon, land_geom):
    """
    Compute fetch statistics from a point.

    Returns (median_fetch_nm, max_fetch_nm, exposure_pct):
      - median_fetch_nm: median over-water distance across all ray directions
      - max_fetch_nm: maximum over-water distance in any direction
      - exposure_pct: fraction of rays reaching > 5nm before hitting land
    """
    point = Point(lon, lat)

    # If point is on land (coastline too coarse), try to nudge to water
    if land_geom.contains(point):
        for r in [0.001, 0.002, 0.005, 0.01, 0.02, 0.05]:
            for a in range(36):
                angle = a * 2 * math.pi / 36
                test_lon = lon + r * math.cos(angle)
                test_lat = lat + r * math.sin(angle)
                if not land_geom.contains(Point(test_lon, test_lat)):
                    lon, lat = test_lon, test_lat
                    break
            else:
                continue
            break
        else:
            return 0.0, 0.0, 0.0  # Fully enclosed by land polygon

    max_dist_deg = MAX_FETCH_NM / 60.0
    fetches = []

    for angle_idx in range(NUM_RAYS):
        angle = angle_idx * 2 * math.pi / NUM_RAYS
        dx = math.cos(angle) * RAY_STEP_DEG
        dy = math.sin(angle) * RAY_STEP_DEG

        dist = 0.0
        cx, cy = lon, lat

        for _ in range(int(max_dist_deg / RAY_STEP_DEG)):
            cx += dx
            cy += dy
            dist += RAY_STEP_DEG

            if land_geom.contains(Point(cx, cy)):
                break

        fetches.append(dist * 60.0)  # degrees → nautical miles

    fetches.sort()
    median = fetches[len(fetches) // 2]
    maximum = fetches[-1]
    exposed = sum(1 for f in fetches if f > 5.0) / len(fetches)

    return median, maximum, exposed


def classify_fetch(median_nm, max_nm, exposure_pct):
    """Classify fartsområde from fetch statistics."""
    for fo in [1, 2, 3, 4]:
        t = THRESHOLDS[fo]
        if median_nm <= t["median_max"] and exposure_pct <= t["exposure_max"]:
            return fo
    return 5


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("FERRY ROUTE FARTSOMRÅDE CLASSIFICATION (Sjøfartsdirektoratet)")
    print("=" * 60)

    if not SAMBAND_FILE.exists():
        print(f"\nERROR: {SAMBAND_FILE} not found")
        sys.exit(1)

    with open(SAMBAND_FILE) as f:
        data = json.load(f)
    print(f"\nLoaded {len(data)} ferry routes")

    # ── Ensure coastline data ─────────────────────────────────────────
    print("\n[1/3] Coastline data...")
    ensure_coastline_data()
    land = load_land_polygon()
    print(f"  Land polygon: {land.geom_type}")

    # ── Classify routes ───────────────────────────────────────────────
    print(f"\n[2/3] Computing fetch for {len(data)} routes...")
    results = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, "ukjent": 0}

    for i, samband in enumerate(data):
        coords = samband.get("coords", [])
        if not coords:
            samband["fartsomrade_sdir"] = "ukjent"
            results["ukjent"] += 1
            continue

        # Sample points along route (every ~5th point + endpoints)
        n = len(coords)
        step = max(1, n // 8)
        indices = sorted(set(list(range(0, n, step)) + [n - 1]))

        all_medians = []
        all_maxes = []
        all_exposures = []

        for idx in indices:
            lat, lon = coords[idx]
            med, mx, exp = compute_fetch_stats(lat, lon, land)
            all_medians.append(med)
            all_maxes.append(mx)
            all_exposures.append(exp)

        route_median = max(all_medians)
        route_max = max(all_maxes)
        route_exposure = max(all_exposures)

        # If ALL points returned 0 fetch → coastline too coarse → ukjent
        if route_max == 0.0:
            samband["fartsomrade_sdir"] = "ukjent"
            results["ukjent"] += 1
        else:
            fo = classify_fetch(route_median, route_max, route_exposure)
            samband["fartsomrade_sdir"] = fo
            results[fo] += 1

        if (i + 1) % 20 == 0 or i == len(data) - 1:
            print(f"  {i + 1}/{len(data)} routes processed...")

    # ── Save results ──────────────────────────────────────────────────
    print(f"\n[3/3] Saving results...")

    with open(SAMBAND_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  JSON: {SAMBAND_FILE}")

    # Export CSV
    csv_path = SAMBAND_FILE.with_suffix(".csv")
    csv_fields = [
        "id", "navn", "type", "status", "fylke", "kontrakt",
        "lat", "lon", "fartsomrade", "fartsomrade_sdir", "eu_havomrade",
        "operator", "match_type", "source_name", "coords",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(";".join(csv_fields) + "\n")
        for d in data:
            row = []
            for field in csv_fields:
                val = d.get(field, "")
                if field == "coords" and isinstance(val, list):
                    val = " | ".join(f"{lat},{lon}" for lat, lon in val)
                row.append(str(val))
            f.write(";".join(row) + "\n")
    print(f"  CSV: {csv_path}")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)

    fo_labels = {
        1: "Helt innelukket farvann",
        2: "Beskyttet farvann",
        3: "Innaskjærs ≤5 nm",
        4: "Innaskjærs ≤25 nm",
        5: "Liten kystfart",
        "ukjent": "Ukjent (coastline too coarse)",
    }

    for k in [1, 2, 3, 4, 5, "ukjent"]:
        count = results[k]
        label = fo_labels[k]
        bar = "#" * min(count, 60)
        print(f"  {str(k):>6}: {count:>4}  {bar}  {label}")
    print(f"\n  Total: {sum(results.values())}")

    # Compare with existing EU classification
    print("\nComparison with EU havområde:")
    for eu in ["B", "C", "D"]:
        routes = [d for d in data if d.get("fartsomrade") == eu]
        if routes:
            fo_dist = {}
            for d in routes:
                fo = d.get("fartsomrade_sdir", "ukjent")
                fo_dist[fo] = fo_dist.get(fo, 0) + 1
            parts = ", ".join(f"FO{k}:{v}" for k, v in sorted(fo_dist.items(), key=lambda x: str(x[0])))
            print(f"  EU {eu} ({len(routes)} routes) → {parts}")


if __name__ == "__main__":
    main()

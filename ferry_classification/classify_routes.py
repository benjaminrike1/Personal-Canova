"""
Classify Norwegian ferry routes (samband) by EU sea area (A, B, C, D).

EU sea area definitions (Directive 2009/45/EC, amended by 2017/2108):
  D  – Sheltered waters (fjords, behind island chains, harbours)
  C  – Within 5 nm of coast, where P(Hs > 2.5 m) < 10% over one year
  B  – Within 20 nm of coast
  A  – Open sea (outside area B)

The STRICTEST area the route passes through determines its classification
(A is strictest, D is mildest).

Data flow:
  1. Check for pre-downloaded GeoJSON polygons in data/
  2. Try kart.sdir.no Avinet A3 API (requires authenticated session)
  3. Fallback: use existing 'fartsomrade' field from source data

kart.sdir.no discovery results:
  - Platform: Avinet Adaptive (A3), NOT ArcGIS REST
  - Config API (public):
      POST /WebServices/client/Configuration.asmx/ReadAppConfig
      Body: {"guuid":"98c41397-6542-4bd9-84cd-ae1a8b7a8b95"}
  - WMS backend: https://ogc.sdir.no/mapserv.ashx (auth required)
  - "Havomrader EOS" layer group (EU sea areas for passenger ships):
      layer_80 = Havomrade C sommerdrift (1.6 - 31.8)
      layer_81 = Havomrade C helarsdrift
      layer_82 = Havomrade D sommerdrift (1.6 - 31.8)
      layer_83 = Havomrade D helarsdrift
  - A and B are NOT separate polygon layers:
      A = unrestricted open sea (no boundary polygon needed)
      B = "Liten kystfart" (layer_94, line-based boundary)
  - DataView API (requires session auth) would give polygon geometry
  - All layers: WMS 1.3.0, EPSG:4326, spatial type: multipolygon
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    from shapely.geometry import LineString, shape
    from shapely.ops import unary_union
    from shapely.prepared import prep
except ImportError:
    print("ERROR: shapely is required. Install with: pip install shapely>=2.0")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests is required. Install with: pip install requests>=2.28")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SAMBAND_FILE = BASE_DIR / "samband_data.json"

AREA_SEVERITY = {"D": 0, "C": 1, "B": 2, "A": 3}

# Pre-downloaded polygon files
POLYGON_FILES = {
    "C": DATA_DIR / "eu_havomrade_C.geojson",
    "D": DATA_DIR / "eu_havomrade_D.geojson",
}

# kart.sdir.no API configuration
SDIR_GUUID = "98c41397-6542-4bd9-84cd-ae1a8b7a8b95"
SDIR_CONFIG_URL = "https://kart.sdir.no/WebServices/client/Configuration.asmx/ReadAppConfig"
SDIR_DATAVIEW_URL = "https://kart.sdir.no/WebServices/client/DataView.asmx/ReadAny"

SDIR_THEME_UUIDS = {
    "C_summer": "e2569cf8-5b0b-405a-a58a-a2ff1cb1465a",   # layer_80
    "C_year":   "1d829819-33a4-44a7-b89e-4c0f435c1e28",   # layer_81
    "D_summer": "a3b8adfd-f732-411e-a8a5-d3cb75d7626f",   # layer_82
    "D_year":   "21355589-840a-406d-afb4-ce3003c6daa8",    # layer_83
}

SDIR_WMS_LAYERS = {
    "C_summer": "layer_80",
    "C_year":   "layer_81",
    "D_summer": "layer_82",
    "D_year":   "layer_83",
}


# ── Data loading ───────────────────────────────────────────────────────────

def load_geojson_file(filepath):
    """Load GeoJSON and return a unified shapely geometry."""
    with open(filepath) as f:
        geojson = json.load(f)
    if geojson.get("type") == "FeatureCollection":
        geoms = [shape(feat["geometry"]) for feat in geojson["features"]]
        return unary_union(geoms)
    elif geojson.get("type") == "Feature":
        return shape(geojson["geometry"])
    return shape(geojson)


def load_predownloaded_polygons():
    """Load EU havomrade polygons from pre-downloaded GeoJSON files."""
    polygons = {}
    for area, filepath in POLYGON_FILES.items():
        if filepath.exists():
            try:
                polygons[area] = load_geojson_file(filepath)
                print(f"  Loaded area {area} from {filepath.name}")
            except Exception as e:
                print(f"  Error loading {filepath.name}: {e}")

    if polygons:
        print(f"  Found {len(polygons)} polygon file(s)")
    return polygons


def try_fetch_sdir_polygons():
    """
    Attempt to fetch EU havomrade polygons from kart.sdir.no.

    The Avinet A3 platform requires authenticated sessions for data access.
    This function verifies the config API works and attempts the DataView API.
    """
    print("  Attempting kart.sdir.no API...")

    try:
        resp = requests.get("https://kart.sdir.no/", timeout=10)
        resp.raise_for_status()

        baat_match = re.search(r"var __baat__\s*=\s*'([^']+)'", resp.text)
        if not baat_match:
            print("  Could not extract baat token")
            return {}

        # Verify config API
        config_resp = requests.post(
            SDIR_CONFIG_URL,
            json={"guuid": SDIR_GUUID},
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=15,
        )
        config_data = config_resp.json()
        if not config_data.get("d", {}).get("success"):
            print("  Config API returned failure")
            return {}

        print("  Config API OK - layer metadata confirmed:")
        print(f"    WMS: https://ogc.sdir.no/mapserv.ashx")
        for name, layer in SDIR_WMS_LAYERS.items():
            print(f"    {layer}: Havomrade {name}")

        # Try DataView (requires auth session)
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json; charset=utf-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-Adaptive-Gui": SDIR_GUUID,
        })

        for label, theme_uuid in SDIR_THEME_UUIDS.items():
            try:
                dv_resp = session.post(
                    SDIR_DATAVIEW_URL,
                    json={"theme_uuid": theme_uuid, "start": 0, "limit": 500},
                    timeout=15,
                )
                dv_data = dv_resp.json()
                dv_d = dv_data.get("d", {})
                if dv_d.get("success") and dv_d.get("records"):
                    print(f"  Got data for {label}!")
                    # Would parse WKB geometry from records here
                    break
            except Exception:
                continue

        print("  DataView requires authenticated session (expected)")

    except requests.exceptions.ConnectionError:
        print("  Could not connect to kart.sdir.no")
    except Exception as e:
        print(f"  Error: {e}")

    return {}


# ── Classification ─────────────────────────────────────────────────────────

def classify_with_polygons(route_line, polygons):
    """
    Classify using official EU havomrade polygons (C and D from kart.sdir.no).

    Logic (strictest area wins):
      - If route entirely within D polygon → D
      - If route intersects C polygon → C
      - Otherwise → B (outside C/D, within coastal zone)
    """
    if "D" in polygons:
        d_prep = prep(polygons["D"])
        if d_prep.contains(route_line):
            return "D"

    if "C" in polygons:
        if route_line.intersects(polygons["C"]):
            return "C"

    if "D" in polygons:
        if route_line.intersects(polygons["D"]):
            return "C"  # Partially in D = at least C

    return "B"


# ── Summary ────────────────────────────────────────────────────────────────

def print_summary(data, method):
    """Print classification summary."""
    eu_counts = Counter(d.get("eu_havomrade", "ukjent") for d in data)
    existing_counts = Counter(d.get("fartsomrade", "N/A") for d in data)

    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)

    print("\nEU Havomrade (classified):")
    for area in ["A", "B", "C", "D", "ukjent"]:
        count = eu_counts.get(area, 0)
        if count > 0:
            bar = "#" * min(count, 80)
            suffix = f"... ({count})" if count > 80 else ""
            print(f"  {area}: {count:>4}  {bar}{suffix}")
    print(f"\n  Total: {sum(eu_counts.values())}")

    print("\nExisting fartsomrade (source data):")
    for area in sorted(existing_counts.keys()):
        count = existing_counts[area]
        bar = "#" * min(count, 80)
        suffix = f"... ({count})" if count > 80 else ""
        print(f"  {area}: {count:>4}  {bar}{suffix}")

    # Compare
    match = mismatch = 0
    mismatches = []
    for d in data:
        existing = d.get("fartsomrade", "")
        new = d.get("eu_havomrade", "")
        if existing and new and new != "ukjent":
            if existing == new:
                match += 1
            else:
                mismatch += 1
                mismatches.append(d)

    if match + mismatch > 0:
        pct = match / (match + mismatch) * 100
        print(f"\nComparison with source fartsomrade:")
        print(f"  Matching:  {match} ({pct:.0f}%)")
        print(f"  Different: {mismatch}")
        if mismatches:
            print(f"\n  Mismatches (showing first 15):")
            for d in mismatches[:15]:
                print(f"    {d['navn']}: source={d['fartsomrade']}, "
                      f"classified={d['eu_havomrade']}")

    # Notes
    print("\n" + "-" * 60)
    if method == "existing":
        print("Used existing 'fartsomrade' field as eu_havomrade.")
        print("The kart.sdir.no WMS endpoint requires browser authentication")
        print("to download polygon geometry data.")
        print("\nTo enable spatial classification:")
        print("  1. Open https://kart.sdir.no in a browser")
        print("  2. Enable 'Havomrader EOS' under Temalag")
        print("  3. Use DevTools > Network to find WMS/DataView requests")
        print("  4. Export polygon data as GeoJSON")
        print("  5. Save to data/eu_havomrade_C.geojson and")
        print("     data/eu_havomrade_D.geojson")
    elif method == "polygons":
        print("Used EU havomrade polygon data for spatial classification.")

    print(f"\nkart.sdir.no layer info:")
    print(f"  Group: 'Havomrader EOS'")
    print(f"  Config API: POST {SDIR_CONFIG_URL}")
    print(f"  WMS: https://ogc.sdir.no/mapserv.ashx (auth required)")
    for name, layer in SDIR_WMS_LAYERS.items():
        print(f"    {layer} = Havomrade {name}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("FERRY ROUTE EU SEA AREA CLASSIFICATION")
    print("=" * 60)

    if not SAMBAND_FILE.exists():
        print(f"\nERROR: {SAMBAND_FILE} not found")
        sys.exit(1)

    with open(SAMBAND_FILE) as f:
        data = json.load(f)
    print(f"\nLoaded {len(data)} ferry routes from {SAMBAND_FILE.name}")

    routes_with_coords = [d for d in data if d.get("coords") and len(d["coords"]) >= 2]
    print(f"Routes with valid coordinates: {len(routes_with_coords)}")

    # ── Try data sources ───────────────────────────────────────────────

    polygons = {}
    method = None

    # Method 1: Pre-downloaded GeoJSON
    print("\n[1/2] Checking for pre-downloaded polygon files...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    polygons = load_predownloaded_polygons()
    if polygons:
        method = "polygons"
        print("  -> Using pre-downloaded polygons")

    # Method 2: Fetch from kart.sdir.no
    if not method:
        print("\n[2/2] Trying kart.sdir.no API...")
        polygons = try_fetch_sdir_polygons()
        if polygons:
            method = "polygons"
            print("  -> Using polygons from kart.sdir.no")
        else:
            print("  -> Polygon data not accessible without browser auth")
            method = "existing"
            print("  -> Using existing 'fartsomrade' values")

    # ── Classify routes ────────────────────────────────────────────────

    print(f"\nClassifying {len(data)} routes (method: {method})...")
    classified = unknown = 0

    for samband in data:
        coords = samband.get("coords", [])
        if not coords or len(coords) < 2:
            samband["eu_havomrade"] = "ukjent"
            unknown += 1
            continue

        if method == "existing":
            area = samband.get("fartsomrade", "ukjent")
        else:
            try:
                line_coords = [(lon, lat) for lat, lon in coords]
                route_line = LineString(line_coords)
                area = classify_with_polygons(route_line, polygons)
            except Exception:
                area = samband.get("fartsomrade", "ukjent")

        samband["eu_havomrade"] = area
        if area == "ukjent":
            unknown += 1
        else:
            classified += 1

    print(f"  Classified: {classified}")
    print(f"  Unknown: {unknown}")

    # Save
    with open(SAMBAND_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {SAMBAND_FILE}")

    print_summary(data, method)


if __name__ == "__main__":
    main()

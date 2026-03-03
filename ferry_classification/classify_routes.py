"""
Classify Norwegian ferry routes (samband) by EU sea area (A, B, C, D).

EU sea area definitions (Directive 2009/45/EC, amended by 2017/2108):
  D  – Sheltered waters (fjords, behind island chains, harbours)
       Within 3 nm of coast, where P(Hs > 1.5 m) < 10% over one year
  C  – Within 5 nm of coast, where P(Hs > 2.5 m) < 10% over one year
  B  – Within 20 nm of coast
  A  – Open sea (outside area B)

The STRICTEST area the route passes through determines its classification
(A is strictest, D is mildest).

Method:
  Primary: WMS pixel sampling from kart.sdir.no official polygon layers.
    Downloads transparent PNG tiles from the WMS for EU havomrade layers
    (layer_81 = C year-round, layer_83 = D year-round) and checks whether
    route coordinates fall within the colored (opaque) polygon areas.
    Uses radius search around each point to handle shore-based coordinates.

  Fallback for routes not in D or C: classified as B (within 20 nm of coast).
  Routes without coordinates: marked as "ukjent" (unknown).

Data sources:
  - kart.sdir.no WMS: ogc.sdir.no/mapserv.ashx (GUI=1 auth)
  - Havomrader EOS layer group (EU sea areas for passenger ships):
      layer_80 = Havomrade C sommerdrift (1.6 - 31.8)
      layer_81 = Havomrade C helarsdrift
      layer_82 = Havomrade D sommerdrift (1.6 - 31.8)
      layer_83 = Havomrade D helarsdrift
"""

import json
import math
import os
import sys
import urllib.request
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests is required. Install with: pip install requests>=2.28")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
TILE_DIR = DATA_DIR / "eu_tiles_rgba"
SAMBAND_FILE = BASE_DIR / "samband_data.json"

WMS_BASE = "https://ogc.sdir.no/mapserv.ashx"
WMS_GUI = "1"

# EU havomrade WMS layers (year-round operation)
WMS_LAYERS = {
    "C": "layer_81",  # Havomrade C helarsdrift
    "D": "layer_83",  # Havomrade D helarsdrift
}

IMG_SIZE = 4096

# Regional tiles covering Norwegian ferry routes
TILES = [
    (58, 5, 61, 10),
    (58, 10, 61, 15),
    (61, 5, 64, 10),
    (61, 10, 64, 15),
    (64, 10, 67, 15),
    (67, 10, 70, 15),
    (67, 15, 70, 20),
    (67, 20, 70, 25),
    (70, 15, 73, 20),
    (70, 20, 73, 25),
    (70, 25, 73, 30),
]

# Radius search parameters
# At 3°lat / 4096px ≈ 80m/px, radius 60px ≈ 5km
RADIUS_D = 60   # Search radius for D polygon (shore→water gap)
RADIUS_C = 40   # Search radius for C polygon


# ── WMS tile download ─────────────────────────────────────────────────────

def download_tile(layer_id, tile):
    """Download a WMS tile as transparent RGBA PNG."""
    lat_min, lon_min, lat_max, lon_max = tile
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": layer_id,
        "CRS": "EPSG:4326",
        "BBOX": f"{lat_min},{lon_min},{lat_max},{lon_max}",
        "WIDTH": str(IMG_SIZE),
        "HEIGHT": str(IMG_SIZE),
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "STYLES": "",
        "GUI": WMS_GUI,
    }
    r = requests.get(WMS_BASE, params=params, timeout=60)
    if "image" not in r.headers.get("content-type", ""):
        return None
    return r.content


def ensure_tiles():
    """Download all WMS tiles if not already cached."""
    TILE_DIR.mkdir(parents=True, exist_ok=True)

    total = len(TILES) * len(WMS_LAYERS)
    done = 0

    for area, layer_id in WMS_LAYERS.items():
        for tile in TILES:
            lat_min, lon_min, lat_max, lon_max = tile
            filename = f"{area}_year_{lat_min}_{lon_min}_{lat_max}_{lon_max}.png"
            filepath = TILE_DIR / filename

            if filepath.exists():
                done += 1
                continue

            print(f"  Downloading {filename}...")
            content = download_tile(layer_id, tile)
            if content and len(content) > 200:
                with open(filepath, "wb") as f:
                    f.write(content)
                done += 1
            else:
                print(f"  WARNING: Failed to download {filename}")
                done += 1

    return done == total


def load_tiles():
    """Load all RGBA tile images into memory."""
    c_tiles = {}
    d_tiles = {}

    for tile in TILES:
        lat_min, lon_min, lat_max, lon_max = tile

        for area, tiles_dict in [("C", c_tiles), ("D", d_tiles)]:
            filename = f"{area}_year_{lat_min}_{lon_min}_{lat_max}_{lon_max}.png"
            filepath = TILE_DIR / filename
            if filepath.exists():
                img = Image.open(filepath)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                tiles_dict[tile] = img

    return c_tiles, d_tiles


# ── Spatial queries ───────────────────────────────────────────────────────

def find_tile(lat, lon):
    """Find which tile contains the given coordinate."""
    for tile in TILES:
        if tile[0] <= lat <= tile[2] and tile[1] <= lon <= tile[3]:
            return tile
    return None


def latlon_to_pixel(lat, lon, tile):
    """Convert lat/lon to pixel coordinates within a tile image."""
    lat_min, lon_min, lat_max, lon_max = tile
    px = int((lon - lon_min) / (lon_max - lon_min) * IMG_SIZE)
    py = int((lat_max - lat) / (lat_max - lat_min) * IMG_SIZE)
    return max(0, min(IMG_SIZE - 1, px)), max(0, min(IMG_SIZE - 1, py))


def is_in_polygon(img, px, py):
    """Check if pixel is inside a polygon (non-transparent)."""
    r, g, b, a = img.getpixel((px, py))
    return a > 30


def search_nearby(img, cx, cy, max_radius):
    """
    Search in expanding circles for a polygon pixel.

    Returns (found, radius_px). Handles the gap between shore-based route
    coordinates and water-only polygon data.
    """
    if 0 <= cx < IMG_SIZE and 0 <= cy < IMG_SIZE:
        if is_in_polygon(img, cx, cy):
            return True, 0

    for r in range(1, max_radius + 1):
        n_points = max(8, r * 4)
        for i in range(n_points):
            angle = i * 2 * math.pi / n_points
            x = cx + int(r * math.cos(angle))
            y = cy + int(r * math.sin(angle))
            if 0 <= x < IMG_SIZE and 0 <= y < IMG_SIZE:
                if is_in_polygon(img, x, y):
                    return True, r
    return False, -1


# ── Route classification ──────────────────────────────────────────────────

def classify_route(coords, c_tiles, d_tiles):
    """
    Classify a route by EU havomrade using WMS pixel sampling.

    For each sampled point along the route, checks the C and D polygon layers.
    Uses radius search to handle shore-based terminal coordinates.

    Logic (strictest area wins):
      - If any point is in C polygon → C
      - If any point is in D polygon → D
      - Otherwise → B (within coastal zone but outside C/D)
    """
    if not coords or len(coords) < 2:
        return "ukjent"

    # Get unique coordinates
    unique_coords = []
    seen = set()
    for lat, lon in coords:
        key = (round(lat, 4), round(lon, 4))
        if key not in seen:
            seen.add(key)
            unique_coords.append((lat, lon))

    # Sample points evenly along route
    if len(unique_coords) <= 30:
        sample = unique_coords
    else:
        n = len(unique_coords)
        step = max(1, n // 25)
        indices = sorted(set(list(range(0, n, step)) + [n - 1]))
        sample = [unique_coords[i] for i in indices]

    c_found = False
    d_found = False

    for lat, lon in sample:
        tile = find_tile(lat, lon)
        if tile is None:
            continue

        px, py = latlon_to_pixel(lat, lon, tile)

        # Check C layer
        if tile in c_tiles and not c_found:
            found, _ = search_nearby(c_tiles[tile], px, py, RADIUS_C)
            if found:
                c_found = True

        # Check D layer
        if tile in d_tiles and not d_found:
            found, _ = search_nearby(d_tiles[tile], px, py, RADIUS_D)
            if found:
                d_found = True

        # C is strictest — if found, no need to continue
        if c_found:
            break

    if c_found:
        return "C"
    elif d_found:
        return "D"
    else:
        return "B"


def refine_b_routes(data, c_tiles, d_tiles):
    """
    Re-check B-classified routes with per-route high-resolution tiles.

    Downloads tight WMS tiles around each B route for better resolution
    in narrow waterways.
    """
    b_routes = [d for d in data if d.get("eu_havomrade") == "B"]
    if not b_routes:
        return

    print(f"  Re-checking {len(b_routes)} B routes with per-route tiles...")
    reclassified = 0

    for d in b_routes:
        coords = d.get("coords", [])
        if not coords:
            continue

        unique = list(set((round(c[0], 4), round(c[1], 4)) for c in coords))
        lat_min = min(c[0] for c in unique) - 0.05
        lat_max = max(c[0] for c in unique) + 0.05
        lon_min = min(c[1] for c in unique) - 0.05
        lon_max = max(c[1] for c in unique) + 0.05

        if lat_max - lat_min < 0.1:
            mid = (lat_max + lat_min) / 2
            lat_min, lat_max = mid - 0.05, mid + 0.05
        if lon_max - lon_min < 0.1:
            mid = (lon_max + lon_min) / 2
            lon_min, lon_max = mid - 0.05, mid + 0.05

        tile_bbox = (lat_min, lon_min, lat_max, lon_max)
        new_area = None

        for area, layer_id in [("C", WMS_LAYERS["C"]), ("D", WMS_LAYERS["D"])]:
            try:
                content = download_tile(layer_id, tile_bbox)
                if not content:
                    continue
                img = Image.open(BytesIO(content))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                w, h = img.size
                for lat, lon in unique:
                    px = int((lon - lon_min) / (lon_max - lon_min) * w)
                    py = int((lat_max - lat) / (lat_max - lat_min) * h)
                    px = max(0, min(w - 1, px))
                    py = max(0, min(h - 1, py))

                    found, _ = search_nearby(img, px, py, 100)
                    if found:
                        new_area = area
                        break
            except Exception:
                continue

            if new_area == "C":
                break

        if new_area:
            d["eu_havomrade"] = new_area
            reclassified += 1
            print(f"    {d['navn']}: B → {new_area}")

    if reclassified:
        print(f"  Reclassified {reclassified} routes")
    else:
        print(f"  All B routes confirmed")


# ── Summary ───────────────────────────────────────────────────────────────

def print_summary(data):
    """Print classification summary."""
    from collections import Counter

    eu_counts = Counter(d.get("eu_havomrade", "ukjent") for d in data)

    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)

    print("\nEU Havomrade (classified):")
    for area in ["A", "B", "C", "D", "ukjent"]:
        count = eu_counts.get(area, 0)
        if count > 0:
            bar = "#" * min(count, 60)
            suffix = f"... ({count})" if count > 60 else ""
            print(f"  {area}: {count:>4}  {bar}{suffix}")
    print(f"\n  Total: {sum(eu_counts.values())}")

    # Show C routes specifically
    c_routes = [d for d in data if d.get("eu_havomrade") == "C"]
    if c_routes:
        print(f"\nRoutes classified as C ({len(c_routes)}):")
        for d in sorted(c_routes, key=lambda x: x["navn"]):
            print(f"  {d['navn']} ({d.get('fylke', '')})")

    # Show B routes
    b_routes = [d for d in data if d.get("eu_havomrade") == "B"]
    if b_routes:
        print(f"\nRoutes classified as B ({len(b_routes)}):")
        for d in sorted(b_routes, key=lambda x: x["navn"]):
            print(f"  {d['navn']} ({d.get('fylke', '')})")

    # Compare with fartsomrade_sdir
    print("\nCross-reference with fartsomrade (Sjøfartsdirektoratet):")
    for eu_area in ["D", "C", "B"]:
        routes = [d for d in data if d.get("eu_havomrade") == eu_area]
        if routes:
            fo_dist = {}
            for d in routes:
                fo = d.get("fartsomrade_sdir", "ukjent")
                fo_dist[fo] = fo_dist.get(fo, 0) + 1
            parts = ", ".join(
                f"FO{k}:{v}" for k, v in sorted(fo_dist.items(), key=lambda x: str(x[0]))
            )
            print(f"  EU {eu_area} ({len(routes)} routes) → {parts}")

    print("\n" + "-" * 60)
    print("Method: WMS pixel sampling from kart.sdir.no")
    print(f"  WMS: {WMS_BASE}")
    print("  Layers: layer_81 (C year-round), layer_83 (D year-round)")


# ── Main ──────────────────────────────────────────────────────────────────

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

    # ── Download WMS tiles ────────────────────────────────────────────
    print("\n[1/3] Ensuring WMS tile data...")
    ensure_tiles()

    print("\n[2/3] Loading tile images...")
    c_tiles, d_tiles = load_tiles()
    print(f"  C tiles: {len(c_tiles)}, D tiles: {len(d_tiles)}")

    if not c_tiles and not d_tiles:
        print("\nERROR: No WMS tiles available. Check network connection.")
        sys.exit(1)

    # ── Classify routes ───────────────────────────────────────────────
    print(f"\n[3/3] Classifying {len(data)} routes...")

    for i, samband in enumerate(data):
        coords = samband.get("coords", [])
        area = classify_route(coords, c_tiles, d_tiles)
        samband["eu_havomrade"] = area

        if (i + 1) % 30 == 0 or i == len(data) - 1:
            print(f"  {i + 1}/{len(data)} routes processed...")

    # Re-check B routes with higher resolution
    refine_b_routes(data, c_tiles, d_tiles)

    # ── Save results ──────────────────────────────────────────────────
    with open(SAMBAND_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {SAMBAND_FILE}")

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
    print(f"Saved CSV to {csv_path}")

    print_summary(data)


if __name__ == "__main__":
    main()

"""
Download summer operation WMS tiles from SDIR and compare with year-round tiles.

Summer layers (1 June - 31 August, more permissive):
  layer_80 = Havomrade C sommerdrift (1.6 - 31.8)
  layer_82 = Havomrade D sommerdrift (1.6 - 31.8)

Year-round layers (existing, stricter):
  layer_81 = Havomrade C helarsdrift
  layer_83 = Havomrade D helarsdrift

Compares opaque pixel counts to identify areas where summer classification
is more permissive (larger polygon = more waters classified as C/D).
"""

import json
import math
import sys
import time
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

# ── Configuration ──────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
TILE_DIR = DATA_DIR / "eu_tiles_rgba"
SAMBAND_FILE = BASE_DIR / "samband_data.json"

WMS_BASE = "https://ogc.sdir.no/mapserv.ashx"

# Summer operation layers
WMS_SUMMER_LAYERS = {
    "C": "layer_80",  # Havomrade C sommerdrift (1.6 - 31.8)
    "D": "layer_82",  # Havomrade D sommerdrift (1.6 - 31.8)
}

# Year-round layers (for reference)
WMS_YEAR_LAYERS = {
    "C": "layer_81",  # Havomrade C helarsdrift
    "D": "layer_83",  # Havomrade D helarsdrift
}

IMG_SIZE = 4096

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


# ── WMS Download ───────────────────────────────────────────────────────

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
        "GUI": "1",
    }
    r = requests.get(WMS_BASE, params=params, timeout=120)
    content_type = r.headers.get("content-type", "")
    if "image" not in content_type:
        print(f"    WARNING: Got content-type '{content_type}' instead of image")
        print(f"    Response (first 500 chars): {r.text[:500]}")
        return None
    return r.content


def download_summer_tiles():
    """Download all summer WMS tiles."""
    TILE_DIR.mkdir(parents=True, exist_ok=True)

    total = len(TILES) * len(WMS_SUMMER_LAYERS)
    downloaded = 0
    skipped = 0
    failed = 0

    for area, layer_id in WMS_SUMMER_LAYERS.items():
        for tile in TILES:
            lat_min, lon_min, lat_max, lon_max = tile
            filename = f"{area}_summer_{lat_min}_{lon_min}_{lat_max}_{lon_max}.png"
            filepath = TILE_DIR / filename

            if filepath.exists():
                print(f"  [skip] {filename} (already exists)")
                skipped += 1
                continue

            print(f"  [download] {filename} (layer={layer_id})...")
            content = download_tile(layer_id, tile)

            if content and len(content) > 200:
                with open(filepath, "wb") as f:
                    f.write(content)
                downloaded += 1
                print(f"    OK ({len(content):,} bytes)")
            else:
                failed += 1
                print(f"    FAILED (content={len(content) if content else 0} bytes)")

            # Brief pause between requests to be polite to the server
            time.sleep(0.5)

    print(f"\n  Summary: {downloaded} downloaded, {skipped} skipped, {failed} failed")
    return failed == 0


# ── Pixel Comparison ───────────────────────────────────────────────────

def count_opaque_pixels(img):
    """Count pixels with alpha > 30 (i.e. inside a polygon)."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    count = 0
    for y in range(h):
        for x in range(w):
            if pixels[x, y][3] > 30:
                count += 1
    return count


def count_opaque_pixels_fast(img):
    """Count pixels with alpha > 30 using numpy for speed."""
    try:
        import numpy as np
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        arr = np.array(img)
        return int(np.sum(arr[:, :, 3] > 30))
    except ImportError:
        return count_opaque_pixels(img)


def find_summer_only_pixels(summer_img, year_img):
    """
    Find pixels that are opaque in summer but transparent in year-round.
    These represent areas where summer classification is MORE permissive.
    Returns count of summer-only pixels.
    """
    try:
        import numpy as np
        s_arr = np.array(summer_img.convert("RGBA"))
        y_arr = np.array(year_img.convert("RGBA"))
        summer_opaque = s_arr[:, :, 3] > 30
        year_opaque = y_arr[:, :, 3] > 30
        summer_only = summer_opaque & ~year_opaque
        year_only = year_opaque & ~summer_opaque
        return int(np.sum(summer_only)), int(np.sum(year_only))
    except ImportError:
        # Slow fallback
        s_px = summer_img.load()
        y_px = year_img.load()
        w, h = summer_img.size
        summer_only = 0
        year_only = 0
        for y in range(h):
            for x in range(w):
                s_opaque = s_px[x, y][3] > 30
                y_opaque = y_px[x, y][3] > 30
                if s_opaque and not y_opaque:
                    summer_only += 1
                elif y_opaque and not s_opaque:
                    year_only += 1
        return summer_only, year_only


def compare_tiles():
    """Compare summer vs year-round tiles pixel by pixel."""
    print("\n" + "=" * 70)
    print("SUMMER vs YEAR-ROUND TILE COMPARISON")
    print("=" * 70)

    results = []

    for area in ["C", "D"]:
        print(f"\n--- Havomrade {area} ---")
        print(f"{'Tile':>30s}  {'Year px':>10s}  {'Summer px':>10s}  {'Diff':>10s}  {'Change':>8s}")
        print("-" * 78)

        for tile in TILES:
            lat_min, lon_min, lat_max, lon_max = tile
            tile_name = f"{lat_min}_{lon_min}_{lat_max}_{lon_max}"

            year_path = TILE_DIR / f"{area}_year_{tile_name}.png"
            summer_path = TILE_DIR / f"{area}_summer_{tile_name}.png"

            if not year_path.exists():
                print(f"  {tile_name:>28s}  {'(no year-round tile)':>40s}")
                continue
            if not summer_path.exists():
                print(f"  {tile_name:>28s}  {'(no summer tile)':>40s}")
                continue

            year_img = Image.open(year_path).convert("RGBA")
            summer_img = Image.open(summer_path).convert("RGBA")

            year_px = count_opaque_pixels_fast(year_img)
            summer_px = count_opaque_pixels_fast(summer_img)

            summer_only, year_only = find_summer_only_pixels(summer_img, year_img)

            diff = summer_px - year_px
            if year_px > 0:
                pct = (diff / year_px) * 100
                pct_str = f"{pct:+.1f}%"
            elif summer_px > 0:
                pct_str = "+inf%"
                pct = float("inf")
            else:
                pct_str = "0.0%"
                pct = 0.0

            larger = "SUMMER" if diff > 0 else ("YEAR" if diff < 0 else "EQUAL")

            print(f"  {tile_name:>28s}  {year_px:>10,}  {summer_px:>10,}  {diff:>+10,}  {pct_str:>8s}")

            results.append({
                "area": area,
                "tile": tile,
                "tile_name": tile_name,
                "year_px": year_px,
                "summer_px": summer_px,
                "diff": diff,
                "pct": pct,
                "summer_only_px": summer_only,
                "year_only_px": year_only,
                "larger": larger,
            })

    return results


# ── Route Classification Comparison ───────────────────────────────────

def latlon_to_pixel(lat, lon, tile):
    """Convert lat/lon to pixel coordinates within a tile image."""
    lat_min, lon_min, lat_max, lon_max = tile
    px = int((lon - lon_min) / (lon_max - lon_min) * IMG_SIZE)
    py = int((lat_max - lat) / (lat_max - lat_min) * IMG_SIZE)
    return max(0, min(IMG_SIZE - 1, px)), max(0, min(IMG_SIZE - 1, py))


def find_tile(lat, lon):
    """Find which tile contains the given coordinate."""
    for tile in TILES:
        if tile[0] <= lat <= tile[2] and tile[1] <= lon <= tile[3]:
            return tile
    return None


def search_nearby(img, cx, cy, max_radius):
    """Search in expanding circles for a polygon pixel."""
    if 0 <= cx < IMG_SIZE and 0 <= cy < IMG_SIZE:
        r, g, b, a = img.getpixel((cx, cy))
        if a > 30:
            return True

    for r in range(1, max_radius + 1):
        n_points = max(8, r * 4)
        for i in range(n_points):
            angle = i * 2 * math.pi / n_points
            x = cx + int(r * math.cos(angle))
            y = cy + int(r * math.sin(angle))
            if 0 <= x < IMG_SIZE and 0 <= y < IMG_SIZE:
                _, _, _, a = img.getpixel((x, y))
                if a > 30:
                    return True
    return False


def classify_route_with_tiles(coords, c_tiles, d_tiles):
    """
    Classify a route by EU havomrade using tile images.
    Returns classification string: "B", "C", or "D".
    """
    if not coords or len(coords) < 2:
        return "ukjent"

    # Deduplicate
    unique_coords = []
    seen = set()
    for lat, lon in coords:
        key = (round(lat, 4), round(lon, 4))
        if key not in seen:
            seen.add(key)
            unique_coords.append((lat, lon))

    # Sample points
    if len(unique_coords) <= 30:
        sample = unique_coords
    else:
        n = len(unique_coords)
        step = max(1, n // 25)
        indices = sorted(set(list(range(0, n, step)) + [n - 1]))
        sample = [unique_coords[i] for i in indices]

    n_sample = len(sample)
    c_found = False
    d_found = False
    unresolved_mid = 0
    total_mid = 0

    RADIUS_C_TERMINAL = 25
    RADIUS_D_TERMINAL = 60
    RADIUS_C_MID = 5
    RADIUS_D_MID = 15

    for idx, (lat, lon) in enumerate(sample):
        tile = find_tile(lat, lon)
        if tile is None:
            continue

        px, py = latlon_to_pixel(lat, lon, tile)
        is_terminal = (idx < 2 or idx >= n_sample - 2)
        r_c = RADIUS_C_TERMINAL if is_terminal else RADIUS_C_MID
        r_d = RADIUS_D_TERMINAL if is_terminal else RADIUS_D_MID

        in_c = False
        in_d = False

        if tile in c_tiles:
            if search_nearby(c_tiles[tile], px, py, r_c):
                in_c = True
                c_found = True

        if tile in d_tiles:
            if search_nearby(d_tiles[tile], px, py, r_d):
                in_d = True
                d_found = True

        if not is_terminal:
            total_mid += 1
            if not in_c and not in_d:
                unresolved_mid += 1

    if c_found and total_mid > 0 and unresolved_mid / total_mid > 0.3:
        return "B"
    if c_found:
        return "C"
    elif d_found:
        return "D"
    else:
        return "B"


def compare_route_classifications():
    """Compare route classifications under summer vs year-round rules."""
    print("\n" + "=" * 70)
    print("ROUTE CLASSIFICATION: SUMMER vs YEAR-ROUND")
    print("=" * 70)

    if not SAMBAND_FILE.exists():
        print(f"  ERROR: {SAMBAND_FILE} not found")
        return []

    with open(SAMBAND_FILE) as f:
        data = json.load(f)
    print(f"\n  Loaded {len(data)} ferry routes")

    # Load year-round tiles
    print("  Loading year-round tiles...")
    c_year = {}
    d_year = {}
    for tile in TILES:
        lat_min, lon_min, lat_max, lon_max = tile
        tile_name = f"{lat_min}_{lon_min}_{lat_max}_{lon_max}"
        c_path = TILE_DIR / f"C_year_{tile_name}.png"
        d_path = TILE_DIR / f"D_year_{tile_name}.png"
        if c_path.exists():
            c_year[tile] = Image.open(c_path).convert("RGBA")
        if d_path.exists():
            d_year[tile] = Image.open(d_path).convert("RGBA")

    # Load summer tiles
    print("  Loading summer tiles...")
    c_summer = {}
    d_summer = {}
    for tile in TILES:
        lat_min, lon_min, lat_max, lon_max = tile
        tile_name = f"{lat_min}_{lon_min}_{lat_max}_{lon_max}"
        c_path = TILE_DIR / f"C_summer_{tile_name}.png"
        d_path = TILE_DIR / f"D_summer_{tile_name}.png"
        if c_path.exists():
            c_summer[tile] = Image.open(c_path).convert("RGBA")
        if d_path.exists():
            d_summer[tile] = Image.open(d_path).convert("RGBA")

    print(f"  Year-round: C={len(c_year)} tiles, D={len(d_year)} tiles")
    print(f"  Summer:     C={len(c_summer)} tiles, D={len(d_summer)} tiles")

    # Classify each route under both regimes
    differences = []
    year_counts = {"B": 0, "C": 0, "D": 0, "ukjent": 0}
    summer_counts = {"B": 0, "C": 0, "D": 0, "ukjent": 0}

    for samband in data:
        coords = samband.get("coords", [])
        name = samband.get("navn", "unknown")

        year_class = classify_route_with_tiles(coords, c_year, d_year)
        summer_class = classify_route_with_tiles(coords, c_summer, d_summer)

        year_counts[year_class] = year_counts.get(year_class, 0) + 1
        summer_counts[summer_class] = summer_counts.get(summer_class, 0) + 1

        if year_class != summer_class:
            differences.append({
                "name": name,
                "year": year_class,
                "summer": summer_class,
                "fylke": samband.get("fylke", ""),
                "kontrakt": samband.get("kontrakt", ""),
                "fartsomrade_orig": samband.get("fartsomrade", ""),
            })

    # Print summary
    print(f"\n  {'Regime':>15s}  {'B':>5s}  {'C':>5s}  {'D':>5s}  {'ukjent':>6s}")
    print(f"  {'-'*40}")
    print(f"  {'Year-round':>15s}  {year_counts.get('B',0):>5}  {year_counts.get('C',0):>5}  {year_counts.get('D',0):>5}  {year_counts.get('ukjent',0):>6}")
    print(f"  {'Summer':>15s}  {summer_counts.get('B',0):>5}  {summer_counts.get('C',0):>5}  {summer_counts.get('D',0):>5}  {summer_counts.get('ukjent',0):>6}")

    if differences:
        print(f"\n  Routes with DIFFERENT classification ({len(differences)}):")
        print(f"  {'Route':<50s}  {'Year':>5s}  {'Summer':>6s}  {'Direction':>12s}  {'Fylke'}")
        print(f"  {'-'*95}")

        # Hierarchy: B > C > D (B is strictest, D is mildest)
        hierarchy = {"B": 1, "C": 2, "D": 3, "ukjent": 0}

        for d in sorted(differences, key=lambda x: x["name"]):
            year_h = hierarchy.get(d["year"], 0)
            summer_h = hierarchy.get(d["summer"], 0)
            if summer_h > year_h:
                direction = "MORE LENIENT"
            elif summer_h < year_h:
                direction = "STRICTER"
            else:
                direction = "CHANGED"
            print(f"  {d['name']:<50s}  {d['year']:>5s}  {d['summer']:>6s}  {direction:>12s}  {d['fylke']}")
    else:
        print(f"\n  No routes have different classification between summer and year-round")

    return differences


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("SUMMER OPERATION WMS TILE DOWNLOAD & COMPARISON")
    print("  Summer layers: layer_80 (C), layer_82 (D)")
    print("  Period: 1 June - 31 August")
    print("=" * 70)

    # Step 1: Download summer tiles
    print("\n[1/3] Downloading summer WMS tiles...")
    download_summer_tiles()

    # Step 2: Compare pixel coverage
    print("\n[2/3] Comparing tile coverage...")
    tile_results = compare_tiles()

    # Summarise which areas are larger in summer
    print("\n" + "=" * 70)
    print("SUMMARY: Which areas are LARGER in summer?")
    print("=" * 70)

    for area in ["C", "D"]:
        area_results = [r for r in tile_results if r["area"] == area]
        total_year = sum(r["year_px"] for r in area_results)
        total_summer = sum(r["summer_px"] for r in area_results)
        total_summer_only = sum(r["summer_only_px"] for r in area_results)
        total_year_only = sum(r["year_only_px"] for r in area_results)

        print(f"\n  Havomrade {area}:")
        print(f"    Year-round total opaque pixels: {total_year:>12,}")
        print(f"    Summer total opaque pixels:     {total_summer:>12,}")
        print(f"    Pixels summer-only (expanded):  {total_summer_only:>12,}")
        print(f"    Pixels year-only (contracted):  {total_year_only:>12,}")

        if total_year > 0:
            net_change = ((total_summer - total_year) / total_year) * 100
            print(f"    Net change: {net_change:+.2f}%")
        elif total_summer > 0:
            print(f"    Net change: summer coverage exists but no year-round coverage")

        larger_tiles = [r for r in area_results if r["diff"] > 0]
        if larger_tiles:
            print(f"    Tiles LARGER in summer ({len(larger_tiles)}):")
            for r in sorted(larger_tiles, key=lambda x: -x["diff"]):
                print(f"      {r['tile_name']}: +{r['diff']:,} px ({r['pct']:+.1f}%)")

    # Step 3: Compare route classifications
    print("\n[3/3] Comparing route classifications...")
    differences = compare_route_classifications()

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()

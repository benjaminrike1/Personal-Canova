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
  1. Primary: WMS pixel sampling from kart.sdir.no official polygon layers.
     Downloads transparent PNG tiles from the WMS for EU havomrade layers
     (layer_81 = C year-round, layer_83 = D year-round) and checks whether
     route coordinates fall within the colored (opaque) polygon areas.
     Uses radius search around each point to handle shore-based coordinates.
     Terminal points (docks) get larger radius; mid-route points use tight
     radius to avoid false matches from nearby polygons.

  2. Mid-route exposure check: If C polygon is found at some points but
     mid-route points are NOT in any polygon (C or D), the route passes
     through B-territory open water → classified as B.

  3. Per-route tile refinement: B-classified routes get re-checked with
     high-resolution per-route WMS tiles for narrow waterways.

  4. Fallback for remaining unresolved routes (still B after refinement):
     - Inland lake routes → "inland" (EU directive does not apply)
     - Short crossings (< 6 km span) → D (clearly sheltered)
     - Otherwise → use original 'fartsomrade' field from data source

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
# At 3°lat / 4096px ≈ 80m/px, so 1px ≈ 80m
#
# Terminal points (docks/shores) need large radius to bridge the gap
# between shore-based coordinates and water-only polygons.
# Mid-route points should be firmly in water — use tight radius to
# avoid grabbing nearby polygons that don't actually cover the route.
RADIUS_D_TERMINAL = 60   # D radius for terminals (~5 km)
RADIUS_C_TERMINAL = 25   # C radius for terminals (~2 km)
RADIUS_D_MID = 15        # D radius for mid-route (~1.2 km)
RADIUS_C_MID = 5         # C radius for mid-route (~400 m)

# Inland ferry routes on freshwater lakes (EU directive does not apply)
INLAND_ROUTES = {"Fjone - Nissedal", "Tangen - Horn"}


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


# ── Helpers ───────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def route_max_span_km(coords):
    """Max distance between any two coordinate pairs (km)."""
    mx = 0.0
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            d = haversine_km(coords[i][0], coords[i][1],
                             coords[j][0], coords[j][1])
            if d > mx:
                mx = d
    return mx


# ── Route classification ──────────────────────────────────────────────────

def classify_route(coords, c_tiles, d_tiles):
    """
    Classify a route by EU havomrade using WMS pixel sampling.

    For each sampled point along the route, checks the C and D polygon layers.
    Terminal points (first/last) get generous search radius to bridge the gap
    between shore-based coordinates and water-only polygons. Mid-route points
    use tight radius — they should be in water where polygons exist, so a
    match at large radius would be a false positive from a nearby zone.

    Logic (strictest area wins):
      - Check ALL sample points (don't stop at first C hit)
      - If C found at some points but mid-route points are outside all
        polygons → route passes through B-territory → B
      - If C found and no unresolved mid-route exposure → C
      - If only D found → D
      - Otherwise → B (will be refined by fallback)
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

    n_sample = len(sample)
    c_found = False
    d_found = False
    unresolved_mid = 0
    total_mid = 0

    for idx, (lat, lon) in enumerate(sample):
        tile = find_tile(lat, lon)
        if tile is None:
            continue

        px, py = latlon_to_pixel(lat, lon, tile)

        # Terminal points (first 2 / last 2) get generous radius
        is_terminal = (idx < 2 or idx >= n_sample - 2)
        r_c = RADIUS_C_TERMINAL if is_terminal else RADIUS_C_MID
        r_d = RADIUS_D_TERMINAL if is_terminal else RADIUS_D_MID

        in_c = False
        in_d = False

        # Check C layer
        if tile in c_tiles:
            found, _ = search_nearby(c_tiles[tile], px, py, r_c)
            if found:
                in_c = True
                c_found = True

        # Check D layer
        if tile in d_tiles:
            found, _ = search_nearby(d_tiles[tile], px, py, r_d)
            if found:
                in_d = True
                d_found = True

        # Track mid-route exposure (points not in any polygon)
        if not is_terminal:
            total_mid += 1
            if not in_c and not in_d:
                unresolved_mid += 1

    # If C found but significant mid-route exposure outside all polygons,
    # the route passes through open water (B territory)
    if c_found and total_mid > 0 and unresolved_mid / total_mid > 0.3:
        return "B"

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
    in narrow waterways. Uses moderate radius (40px) — enough to bridge
    shore→water gap but not so large as to grab unrelated polygons.
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

                    found, _ = search_nearby(img, px, py, 40)
                    if found:
                        new_area = area
                        break
            except Exception:
                continue

            if new_area == "C":
                break

        if new_area:
            d["eu_havomrade"] = new_area
            d["eu_havomrade_method"] = "wms_refined"
            reclassified += 1
            print(f"    {d['navn']}: B → {new_area}")

    if reclassified:
        print(f"  Reclassified {reclassified} routes")
    else:
        print(f"  No routes reclassified by per-route tiles")


def apply_fallback_classification(data):
    """
    Classify routes that WMS polygons could not resolve.

    After WMS classification + per-route refinement, remaining B routes
    are ones where the SDIR polygon simply doesn't cover the waterway
    (narrow fjords, small straits) or are genuinely in open water.

    Fallback strategy:
      1. Inland lake routes → "inland" (EU directive not applicable)
      2. Short crossings (< 6 km) → D (clearly sheltered narrow waterways)
      3. Original 'fartsomrade' field → use as-is (B, C, or D)
    """
    b_routes = [d for d in data if d.get("eu_havomrade") == "B"]
    if not b_routes:
        return

    print(f"\n  Applying fallback for {len(b_routes)} unresolved routes...")
    changes = {"D": 0, "C": 0, "B": 0, "inland": 0}

    for route in b_routes:
        name = route.get("navn", "")

        # 1. Inland lakes
        if name in INLAND_ROUTES:
            route["eu_havomrade"] = "inland"
            route["eu_havomrade_method"] = "inland_lake"
            changes["inland"] += 1
            print(f"    {name}: B → inland (freshwater lake)")
            continue

        fo_orig = route.get("fartsomrade", "")
        coords = route.get("coords", [])
        span_km = route_max_span_km(coords) if coords else 0

        # 2. If original says B, trust it (genuinely exposed)
        if fo_orig == "B":
            route["eu_havomrade_method"] = "fallback_original"
            changes["B"] += 1
            print(f"    {name}: B confirmed (original={fo_orig}, span={span_km:.1f}km)")
            continue

        # 3. Short crossings → D (sheltered narrow waterways not covered by WMS)
        if span_km < 6.0:
            route["eu_havomrade"] = "D"
            route["eu_havomrade_method"] = "fallback_sheltered"
            changes["D"] += 1
            print(f"    {name}: B → D (sheltered, span={span_km:.1f}km)")
            continue

        # 4. Use original classification as fallback
        if fo_orig in ("C", "D"):
            route["eu_havomrade"] = fo_orig
            route["eu_havomrade_method"] = "fallback_original"
            changes[fo_orig] += 1
            print(f"    {name}: B → {fo_orig} (original={fo_orig}, span={span_km:.1f}km)")
        else:
            route["eu_havomrade_method"] = "fallback_default"
            changes["B"] += 1
            print(f"    {name}: B confirmed (no fallback data)")

    parts = ", ".join(f"{k}={v}" for k, v in sorted(changes.items()) if v)
    print(f"  Fallback results: {parts}")


def cross_check_classification(data):
    """
    Final cross-check: override WMS classification when it conflicts with
    strong evidence from the original regulatory classification.

    Specifically: if a long route has fo_orig=B (genuinely exposed open-water
    route), the WMS finding C at an endpoint doesn't mean the whole route is C.
    The mid-route open water makes it B.
    """
    overrides = 0
    for route in data:
        eu = route.get("eu_havomrade")
        fo_orig = route.get("fartsomrade", "")
        fo_sdir = route.get("fartsomrade_sdir", "ukjent")
        span = route_max_span_km(route.get("coords", []))

        # Route classified as C but original says B and it's a long exposed route
        if eu == "C" and fo_orig == "B" and span > 20.0:
            route["eu_havomrade"] = "B"
            route["eu_havomrade_method"] = "cross_check"
            overrides += 1
            print(f"    {route['navn']}: C → B (original=B, span={span:.1f}km)")

    if overrides:
        print(f"  Cross-check overrode {overrides} routes")


# ── Summary ───────────────────────────────────────────────────────────────

def print_summary(data):
    """Print classification summary."""
    from collections import Counter

    eu_counts = Counter(d.get("eu_havomrade", "ukjent") for d in data)

    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)

    print("\nEU Havomrade (classified):")
    for area in ["A", "B", "C", "D", "inland", "ukjent"]:
        count = eu_counts.get(area, 0)
        if count > 0:
            bar = "#" * min(count, 60)
            suffix = f"... ({count})" if count > 60 else ""
            print(f"  {area:>6}: {count:>4}  {bar}{suffix}")
    print(f"\n  Total: {sum(eu_counts.values())}")

    # Show inland routes
    inland = [d for d in data if d.get("eu_havomrade") == "inland"]
    if inland:
        print(f"\nInland routes ({len(inland)}) — EU directive not applicable:")
        for d in sorted(inland, key=lambda x: x["navn"]):
            print(f"  {d['navn']} ({d.get('fylke', '')})")

    # Show C routes
    c_routes = [d for d in data if d.get("eu_havomrade") == "C"]
    if c_routes:
        print(f"\nRoutes classified as C ({len(c_routes)}):")
        for d in sorted(c_routes, key=lambda x: x["navn"]):
            method = d.get("eu_havomrade_method", "wms")
            span = route_max_span_km(d.get("coords", []))
            print(f"  {d['navn']:50s} {span:5.1f}km  [{method}]")

    # Show B routes
    b_routes = [d for d in data if d.get("eu_havomrade") == "B"]
    if b_routes:
        print(f"\nRoutes classified as B ({len(b_routes)}):")
        for d in sorted(b_routes, key=lambda x: x["navn"]):
            method = d.get("eu_havomrade_method", "wms")
            span = route_max_span_km(d.get("coords", []))
            print(f"  {d['navn']:50s} {span:5.1f}km  [{method}]")

    # Compare with fartsomrade_sdir
    print("\nCross-reference with fartsomrade_sdir (fetch-based):")
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

    # Show method breakdown
    method_counts = Counter(d.get("eu_havomrade_method", "wms") for d in data)
    print(f"\nClassification method breakdown:")
    for method, count in sorted(method_counts.items()):
        print(f"  {method}: {count}")

    print("\n" + "-" * 60)
    print("Method: WMS pixel sampling from kart.sdir.no + fallback")
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
    print("\n[1/6] Ensuring WMS tile data...")
    ensure_tiles()

    print("\n[2/6] Loading tile images...")
    c_tiles, d_tiles = load_tiles()
    print(f"  C tiles: {len(c_tiles)}, D tiles: {len(d_tiles)}")

    if not c_tiles and not d_tiles:
        print("\nERROR: No WMS tiles available. Check network connection.")
        sys.exit(1)

    # ── Classify routes ───────────────────────────────────────────────
    print(f"\n[3/6] Classifying {len(data)} routes (WMS pixel sampling)...")

    for i, samband in enumerate(data):
        coords = samband.get("coords", [])
        area = classify_route(coords, c_tiles, d_tiles)
        samband["eu_havomrade"] = area
        samband["eu_havomrade_method"] = "wms"

        if (i + 1) % 30 == 0 or i == len(data) - 1:
            print(f"  {i + 1}/{len(data)} routes processed...")

    from collections import Counter
    initial = Counter(d["eu_havomrade"] for d in data)
    print(f"  Initial: D={initial.get('D',0)}, C={initial.get('C',0)}, B={initial.get('B',0)}")

    # Re-check B routes with higher resolution per-route tiles
    print(f"\n[4/6] Refining B routes with per-route WMS tiles...")
    refine_b_routes(data, c_tiles, d_tiles)

    # Apply fallback classification for remaining unresolved routes
    print(f"\n[5/6] Fallback classification for unresolved routes...")
    apply_fallback_classification(data)

    # Cross-check: override when WMS conflicts with strong evidence
    print(f"\n[6/6] Cross-checking classifications...")
    cross_check_classification(data)

    # ── Save results ──────────────────────────────────────────────────
    with open(SAMBAND_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {SAMBAND_FILE}")

    # Export CSV
    csv_path = SAMBAND_FILE.with_suffix(".csv")
    csv_fields = [
        "id", "navn", "type", "status", "fylke", "kontrakt",
        "lat", "lon", "fartsomrade", "fartsomrade_sdir", "eu_havomrade",
        "eu_havomrade_method",
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

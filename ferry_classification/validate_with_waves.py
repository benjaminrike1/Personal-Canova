"""
Validate EU sea area classification using NORAC 800m wave hindcast data.

Computes exceedance probabilities from MET Norway's NORAC coastal wave
hindcast (800m resolution) to independently verify D/C/B classification.

EU directive thresholds:
  D: P(Hs > 1.5 m) < 10% over one year
  C: P(Hs > 2.5 m) < 10% over one year
  B: Within 20 nm of coast (no wave criterion)

Requirements:
  pip install metocean-api pandas

Usage:
  python validate_with_waves.py

NOTE: Requires network access to thredds.met.no (OPeNDAP).
      Will NOT work from sandboxed/restricted environments.
"""

import json
import math
import sys
from pathlib import Path

try:
    from metocean_api import ts
    import pandas as pd
except ImportError:
    print("ERROR: Install dependencies: pip install metocean-api pandas")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
SAMBAND_FILE = BASE_DIR / "samband_data.json"

# Routes to validate (prioritized)
PRIORITY_ROUTES = {
    # Fallback C routes (no WMS confirmation) — highest priority
    "Askvoll-Fure-Gjervik-Askvoll",
    "Askvoll-Fure-Værlandet",
    "Fjelberg-Sydnes-Utbjoa",
    "Husavik - Sandvikvåg",
    "Mekjarvik - Kvitsøy",
    "Mortavika - Arsvågen",
    "Skjersholmane - Ranavik",
    "Stavanger - Hommersåk",
    # D routes with FO5 exposure — suspicious
    "Stokkvågen-Onøy-Sleneset-Lovund",
    "Igerøy -Tjøtta",
    "Ørnes-Vassdalsvik-Meløysund-Bolga",
    "Dyrøy-Øyrekken",
    "Horn - Igerøy",
    # D routes with ship class B — suspicious
    "Edøya-Sandvika",
    "Seivika-Tømmervåg",
}


def get_route_midpoint(coords):
    """Get the midpoint of a route (middle coordinate)."""
    if not coords:
        return None, None
    mid = len(coords) // 2
    return coords[mid][0], coords[mid][1]


def fetch_wave_stats(lat, lon, name):
    """Fetch NORAC wave data and compute exceedance stats."""
    try:
        df = ts.TimeSeries(
            lon=lon, lat=lat,
            start_time='2000-01-01',
            end_time='2023-12-31',
            product='NORAC_wave'
        )
        df.import_data(save_csv=False, save_nc=False)
        wave_data = df.data

        # Find Hs column
        hs_col = None
        for col in wave_data.columns:
            if 'hs' in col.lower() or 'swh' in col.lower():
                hs_col = col
                break

        if hs_col is None:
            # Try NORA3 as fallback
            df = ts.TimeSeries(
                lon=lon, lat=lat,
                start_time='2000-01-01',
                end_time='2023-12-31',
                product='NORA3_wave_sub'
            )
            df.import_data(save_csv=False, save_nc=False)
            wave_data = df.data
            for col in wave_data.columns:
                if 'hs' in col.lower() or 'swh' in col.lower():
                    hs_col = col
                    break

        if hs_col is None:
            return None

        hs = wave_data[hs_col].dropna()

        return {
            "n_records": len(hs),
            "hs_mean": round(hs.mean(), 2),
            "hs_p50": round(hs.median(), 2),
            "hs_p95": round(hs.quantile(0.95), 2),
            "hs_max": round(hs.max(), 2),
            "p_exceed_1_5m": round((hs > 1.5).mean() * 100, 2),
            "p_exceed_2_5m": round((hs > 2.5).mean() * 100, 2),
        }
    except Exception as e:
        print(f"    Error for {name}: {e}")
        return None


def classify_from_waves(stats):
    """Classify EU area from wave exceedance stats."""
    if stats is None:
        return "?"
    if stats["p_exceed_1_5m"] < 10:
        return "D"
    elif stats["p_exceed_2_5m"] < 10:
        return "C"
    else:
        return "B"


def main():
    print("=" * 70)
    print("WAVE-BASED VALIDATION OF EU SEA AREA CLASSIFICATION")
    print("Using NORAC 800m coastal wave hindcast (MET Norway)")
    print("=" * 70)

    with open(SAMBAND_FILE) as f:
        data = json.load(f)

    targets = [d for d in data if d.get("navn") in PRIORITY_ROUTES]
    print(f"\nValidating {len(targets)} priority routes...\n")

    results = []
    header = f"{'Route':<45s} {'lat':>7s} {'lon':>7s} {'P>1.5m':>7s} {'P>2.5m':>7s} {'Wave':>5s} {'Curr':>5s} {'Match':>6s}"
    print(header)
    print("-" * len(header))

    for d in sorted(targets, key=lambda x: x["navn"]):
        lat, lon = get_route_midpoint(d.get("coords", []))
        if lat is None:
            continue

        name = d["navn"]
        current_eu = d.get("eu_havomrade", "?")

        print(f"  {name:<43s} {lat:7.3f} {lon:7.3f} ", end="", flush=True)

        stats = fetch_wave_stats(lat, lon, name)
        wave_eu = classify_from_waves(stats)

        if stats:
            match = "OK" if wave_eu == current_eu else "DIFF"
            print(f"{stats['p_exceed_1_5m']:6.1f}% {stats['p_exceed_2_5m']:6.1f}% {wave_eu:>5s} {current_eu:>5s} {match:>6s}")

            results.append({
                "navn": name,
                "lat": lat,
                "lon": lon,
                "current_eu": current_eu,
                "wave_eu": wave_eu,
                "match": match == "OK",
                **stats,
            })
        else:
            print(f"{'?':>7s} {'?':>7s} {'?':>5s} {current_eu:>5s} {'FAIL':>6s}")

    # Summary
    if results:
        matches = sum(1 for r in results if r["match"])
        total = len(results)
        print(f"\n{'=' * 70}")
        print(f"VALIDATION SUMMARY: {matches}/{total} routes match ({matches/total*100:.0f}%)")

        diffs = [r for r in results if not r["match"]]
        if diffs:
            print(f"\nDISAGREEMENTS ({len(diffs)}):")
            for r in diffs:
                print(f"  {r['navn']}: current={r['current_eu']}, "
                      f"wave={r['wave_eu']} "
                      f"(P>1.5m={r['p_exceed_1_5m']:.1f}%, "
                      f"P>2.5m={r['p_exceed_2_5m']:.1f}%)")

        # Save results
        out_path = BASE_DIR / "wave_validation_results.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nSaved detailed results to {out_path}")


if __name__ == "__main__":
    main()

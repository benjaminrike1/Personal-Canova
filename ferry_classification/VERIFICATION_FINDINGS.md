# EU Sea Area Classification — Verification Findings

## Summary of Investigations

Six verification actions were performed to assess the quality of the EU sea area
(havomrade) classification for 141 Norwegian ferry routes.

### Current Classification (v2)

| Area   | Count | Description                    |
|--------|-------|--------------------------------|
| D      | 121   | Sheltered waters               |
| C      |  16   | Within 5 nm, moderate exposure |
| B      |   2   | Within 20 nm, exposed          |
| inland |   2   | Freshwater lakes (N/A)         |

---

## A: WMS Polygon Overlap — C and D are mostly exclusive zones

**Finding:** C and D polygons overlap by ~5% of C pixels (150,098 pixels).
The overlap occurs at polygon boundaries and is consistent with edge
anti-aliasing rather than systematic overlap. D is 3.3x larger than C,
reflecting Norway's predominantly sheltered fjord coastline.

**Implication:** Our classification logic (check C then D) is correct.
At boundary pixels where both are opaque, classifying as C (stricter) is
the right behavior. The polygons represent separate geographic zones with
minor boundary overlap, NOT nested areas.

---

## B: Spot-check Against SDIR Interactive Map

Per-route WMS tiles downloaded for 6 suspect routes. Each route's
coordinates checked against both C (layer_81) and D (layer_83) polygons.

| Route                        | C layer | D layer | Class | Verdict              |
|------------------------------|---------|---------|-------|----------------------|
| Edøya-Sandvika (fo_orig=B)   | 0%      | 90%     | D     | CONFIRMED by WMS     |
| Seivika-Tømmervåg (fo_orig=B)| 0%      | 94%     | D     | CONFIRMED by WMS     |
| Stokkvågen-Lovund (FO5)      | 0%      | 76%     | D     | CONFIRMED by WMS     |
| Igerøy-Tjøtta (FO5)          | 0%      | 88%     | D     | CONFIRMED by WMS     |
| Askvoll-Fure-Værlandet       | 0%      | 0%      | C     | No polygon coverage  |
| Mortavika-Arsvågen            | 0%      | 0%      | C     | No polygon coverage  |

**Key findings:**
- The 4 suspect D routes are CONFIRMED as D by SDIR's official WMS data.
  fo_orig=B reflects ship class (overqualified), FO5 reflects Norwegian
  fartsområde (coastal navigation behind islands), both consistent with D.
- The 2 fallback C routes have NO SDIR polygon coverage at all (neither C
  nor D). The Boknafjord (Mortavika) and outer Askvoll waters are genuine
  WMS gaps. C is a reasonable conservative default for these exposed crossings.

---

## C: What Does the 'fartsomrade' Field Actually Represent?

**CRITICAL FINDING:** The `fartsomrade` field (values B, C, D) in the source
data almost certainly records the **passenger ship class certification**,
NOT the EU sea area of the route.

Evidence:
- 128 of 141 routes (91%) have fartsomrade=C, which is inconsistent with
  actual sea area distribution (SDIR's own WMS shows 121 routes in area D)
- A Class C ship is certified to operate in BOTH areas C and D
- Most Norwegian ferry operators use Class C certified ships for operational
  flexibility, even when routes are entirely within area D
- The Norwegian FO system (1-5) maps: FO3→D, FO4→C, FO5→B. Most ferry
  routes are FO1-3, confirming D is the dominant sea area.

**Impact on classification:**
- The `fartsomrade` field should NOT be treated as ground truth for EU area
- The "disagreement" between fartsomrade=C and eu_havomrade=D is expected:
  ships hold Class C certificates while operating in sea area D
- Fallback classifications using fartsomrade are NOT validated by this field
- The 8 fallback_original C routes remain as C (conservative default for
  routes outside the D polygon), but the justification changes: they are C
  because they're outside confirmed D territory, not because fartsomrade=C

---

## D: Higher-Resolution Coastline (GSHHG)

**Finding:** Even GSHHG high-resolution coastline (~200m) cannot resolve
18 of 21 previously-unknown routes. Only 2 additional routes were resolved:
- Barmen-Barmsund → FO1 (fully sheltered) ✓ confirms D
- Finnøyferjen → FO1 (fully sheltered) ✓ confirms D

The remaining 18 routes are in fjords/waterways narrower than 200m that
neither Natural Earth 10m nor GSHHG can resolve. OSM coastline data
(meter-level resolution) would be needed but was unavailable via Overpass API.

**Implication:** Coastline-based fetch analysis has fundamental resolution
limits for narrow Norwegian waterways. Alternative validation methods
(wave data, manual inspection) are needed.

---

## E: Wave/Weather Data Sources (MET Norway)

**Finding:** MET Norway provides excellent wave hindcast data for validation:

| Dataset         | Resolution | Best for                          |
|-----------------|------------|-----------------------------------|
| NORAC wave      | 800 m      | Fjords, sheltered coastal waters  |
| NORA3 wave      | 3 km       | Open fjords, exposed crossings    |
| NORA10          | 10 km      | Open sea (too coarse for ferries) |

**How to use:**
```python
from metocean_api import ts
df = ts.TimeSeries(
    lon=5.32, lat=60.39,
    start_time='1990-01-01', end_time='2023-12-31',
    product='NORAC_wave'  # 800m coastal
)
df.import_data(save_csv=True)
# Then compute: P(Hs > 1.5m) for area D, P(Hs > 2.5m) for area C
```

**Recommendation:** This is the single best validation method. NORAC at 800m
can resolve wave sheltering in fjords. Computing exceedance probabilities
gives objective D/C classification matching the EU directive definitions.

---

## F: Summer vs Year-Round Classification

**Finding:** Summer polygons are larger (D: +17%, C: +55%), reflecting
calmer summer seas. Only 2 routes change classification:

| Route                    | Year-round | Summer | Direction     |
|--------------------------|------------|--------|---------------|
| Risør-Øysang             | C          | D      | More lenient  |
| Svolvær-Skrova-Skutvik   | C          | D      | More lenient  |

**Implication:** The summer/winter distinction has minimal practical impact
(2 of 141 routes). Year-round classification is the conservative choice
and appropriate for general analysis. Summer tiles are now cached for
future use if seasonal analysis is needed.

---

## Remaining Concerns and Recommended Next Steps

### High confidence (121 routes — 86%)
- 113 routes classified D by WMS primary pass
- 8 routes classified D by fallback_sheltered (span < 6 km)
- These are well-supported by WMS polygon data and geographic analysis

### Medium confidence (16 routes — 11%)
- 8 routes classified C by WMS primary pass — well-supported
- 8 routes classified C by fallback — conservative default, not WMS-confirmed
  - Recommendation: validate with NORAC 800m wave data

### High confidence — special cases (4 routes — 3%)
- 2 B routes (Haugesund-Utsira, Bodo-Varoy-Rost-Moskenes) — correct
- 2 inland routes (Fjone-Nissedal, Tangen-Horn) — correct

### Priority validation targets
1. The 8 fallback_original C routes (no WMS confirmation)
2. The 10 D routes with FO5 fetch exposure (WMS says D but fetch says exposed)
3. The 2 D routes with fartsomrade=B ship class (Edoya-Sandvika, Seivika-Tommervag)

### Recommended validation method
Install `metocean-api` and `metocean-stats`, extract NORAC 800m wave data
for ~20 suspect route midpoints, compute P(Hs > 1.5m) and P(Hs > 2.5m),
and compare against current classification.

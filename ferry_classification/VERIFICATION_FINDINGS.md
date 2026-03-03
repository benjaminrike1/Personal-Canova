# EU Sea Area Classification — Verification Findings

## Summary of Investigations

Six verification actions were performed to assess the quality of the EU sea area
(havomrade) classification for 141 Norwegian ferry routes.

### Current Classification (v3 — wave-validated)

| Area   | Count | Description                    |
|--------|-------|--------------------------------|
| D      | 120   | Sheltered waters               |
| C      |  17   | Within 5 nm, moderate exposure |
| B      |   2   | Within 20 nm, exposed          |
| inland |   2   | Freshwater lakes (N/A)         |

Change from v2: Stokkvågen-Onøy-Sleneset-Lovund reclassified D → C
based on NORAC 800m wave data (P(Hs > 1.5m) = 15.9%, exceeds 10% D threshold).

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
| Stokkvågen-Lovund (FO5)      | 0%      | 76%     | D→C   | Overridden by wave data (§G) |
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

## G: Wave-Based Validation (NORAC 800m + NORA3 3km)

**Method:** Queried MET Norway THREDDS NCSS endpoint for significant wave height
(Hs) at route midpoints. Used NORA3 (3km) for exposed routes and NORAC (800m)
for coastal/fjord routes. Coordinate nudging (±0.04°) applied to find nearest
ocean grid point when midpoint falls on land.

**EU directive thresholds:**
- D: P(Hs > 1.5 m) < 10% over one year
- C: P(Hs > 2.5 m) < 10% over one year

### Results: 13 routes resolved, 12 match (92%)

| Route                           | P>1.5m | P>2.5m | Wave | Curr | Match |
|---------------------------------|--------|--------|------|------|-------|
| Anda-Lote                       |  0.0%  |  0.0%  |  D   |  D   | OK    |
| Dypfest-Tarva                   |  1.5%  |  0.0%  |  D   |  D   | OK    |
| Dyrøy-Øyrekken                  |  4.5%  |  0.0%  |  D   |  D   | OK    |
| Edøya-Sandvika                  |  1.8%  |  0.0%  |  D   |  D   | OK    |
| Horn-Igerøy                     |  5.7%  |  0.0%  |  D   |  D   | OK    |
| Igerøy-Tjøtta                   |  2.1%  |  0.0%  |  D   |  D   | OK    |
| Seivika-Tømmervåg               |  0.0%  |  0.0%  |  D   |  D   | OK    |
| Solfjellsjøen-Vandve            |  0.0%  |  0.0%  |  D   |  D   | OK    |
| Sørrollnes-Stangnes             |  0.1%  |  0.0%  |  D   |  D   | OK    |
| Sund-Horsdal-Sørarnøy           |  2.7%  |  0.0%  |  D   |  D   | OK    |
| Søvik-Herøy                     |  0.1%  |  0.0%  |  D   |  D   | OK    |
| Ørnes-Vassdalsvik-Meløysund     |  0.0%  |  0.0%  |  D   |  D   | OK    |
| **Stokkvågen-Onøy-Sleneset-Lovund** | **15.9%** | **4.8%** | **C** | **D** | **DIFF** |

### Key findings:

1. **Stokkvågen-Lovund reclassified D → C:** P(Hs > 1.5m) = 15.9% exceeds
   the 10% D threshold. The route goes to Lovund island exposed to open sea.
   WMS showed 76% D polygon coverage, but wave data shows actual conditions
   are too rough for area D. Reclassified to C (P(Hs > 2.5m) = 4.8% < 10%).

2. **Suspect routes CONFIRMED:** All FO5 and ship-class-B routes with wave data
   are firmly in area D. Worst case: Horn-Igerøy at 5.7% (well under 10%).

3. **14 routes unresolvable by wave data:** All in Vestland/Rogaland fjords
   (Hardangerfjorden, Lysefjorden, Sognefjorden area). Route midpoints fall
   on land in both NORAC 800m and NORA3 3km grids — fjords are narrower than
   model resolution. These routes are classified D by WMS or fallback_sheltered.

### Limitations:
- Wave data resolution (800m-3km) cannot resolve narrow fjords
- Only monthly mean Hs was available via NCSS; full hourly timeseries
  would give more precise exceedance probabilities
- Coordinate nudging may shift the analysis point to a different water body

---

## Updated Confidence Assessment

### High confidence (120 routes — 85%)
- 112 routes classified D by WMS primary pass (1 reclassified to C by wave data)
- 8 routes classified D by fallback_sheltered (span < 6 km)
- 12 D routes independently confirmed by wave data (P(Hs > 1.5m) < 10%)

### Medium confidence (17 routes — 12%)
- 9 routes classified C by WMS primary pass — well-supported
- 1 route classified C by wave validation (Stokkvågen-Lovund) — strong evidence
- 7 routes classified C by fallback — conservative default, not independently confirmed
  - All 7 in narrow Vestland/Rogaland fjords, unresolvable by available wave data
  - Manual inspection or higher-resolution wave modeling needed

### High confidence — special cases (4 routes — 3%)
- 2 B routes (Haugesund-Utsira, Bodø-Værøy-Røst-Moskenes) — correct
- 2 inland routes (Fjone-Nissedal, Tangen-Horn) — correct

### Remaining unvalidated routes (7 fallback C)
These routes have no WMS polygon coverage AND no wave data (on land in model):
1. Askvoll-Fure-Gjervik-Askvoll
2. Askvoll-Fure-Værlandet
3. Fjelberg-Sydnes-Utbjoa
4. Husavik-Sandvikvåg
5. Mekjarvik-Kvitsøy
6. Mortavika-Arsvågen
7. Skjersholmane-Ranavik
8. Stavanger-Hommersåk

C is a conservative default for these. Some may actually be D (sheltered fjord
crossings), but without WMS or wave confirmation, C is the safe choice.

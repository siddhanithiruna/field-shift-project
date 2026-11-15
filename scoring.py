# scoring.py -- indicators + rotation scoring (POWER + optional NDVI)
import pandas as pd
from rotations import ROTATIONS

GROWING_MONTHS = (5, 9)      # May-Sep
SUMMER_MONTHS = (6, 8)       # Jun-Aug (peak crop greenness)
DRY_SOIL_THRESHOLD = 0.40    # root-zone wetness below this = dry day
HOT_DAY_C = 35               # max temp at/above this = heat-stress day

# ---------------- Data loading ----------------
def load_power(path="data/power_iowa.csv"):
    return pd.read_csv(path, parse_dates=["date"], index_col="date")

def load_ndvi(path="data/ndvi_iowa.csv"):
    """Clean AppEEARS MOD13Q1 export -> DataFrame indexed by date with one 'ndvi' column."""
    raw = pd.read_csv(path, parse_dates=["Date"])
    ndvi_col = [c for c in raw.columns if c.endswith("_NDVI")][0]
    out = pd.DataFrame({"date": raw["Date"], "ndvi": raw[ndvi_col]})
    # drop cloudy pixels and impossible values
    cloudy = raw.filter(like="MODLAND_Description").iloc[:, 0].str.contains("cloud", case=False, na=False)
    out = out[~cloudy & (out["ndvi"] > 0)]
    return out.set_index("date").sort_index()

# ---------------- Yearly summaries ----------------
def growing_season(df):
    return df[(df.index.month >= GROWING_MONTHS[0]) & (df.index.month <= GROWING_MONTHS[1])]

def yearly_table(df):
    """Per-year growing-season stats (used for charts + trends)."""
    gs = growing_season(df)
    g = gs.groupby(gs.index.year)
    return pd.DataFrame({
        "rain_mm": g["PRECTOTCORR"].sum(),
        "hot_days": g["T2M_MAX"].apply(lambda s: int((s >= HOT_DAY_C).sum())),
        "dry_soil_pct": g["GWETROOT"].apply(lambda s: (s < DRY_SOIL_THRESHOLD).mean() * 100),
        "soil_wetness": g["GWETROOT"].mean(),
    }).round(2)

def ndvi_yearly(ndvi):
    """Mean Jun-Aug NDVI per year (peak crop vigor)."""
    s = ndvi[(ndvi.index.month >= SUMMER_MONTHS[0]) & (ndvi.index.month <= SUMMER_MONTHS[1])]
    out = s.groupby(s.index.year)["ndvi"].mean().round(3).to_frame("summer_ndvi")
    return out[out.index >= 2019]   # drop partial 2018 data point

def _scale(x, lo, hi):
    """Clamp-scale x to 0-1 between lo and hi."""
    return float(max(0.0, min(1.0, (x - lo) / (hi - lo))))

# ---------------- Indicators ----------------
def compute_indicators(df, drought_boost=0.0, heat_boost=0.0, ndvi=None):
    """
    All indicators on a 0-1 scale (1 = worse / more stress).
    drought_boost / heat_boost (0-1) power the what-if sliders.
    ndvi: optional DataFrame from load_ndvi() -> adds 'veg_decline'.
    """
    yt = yearly_table(df)
    recent = yt.tail(3)

    drought = _scale(recent["dry_soil_pct"].mean(), 0, 50)
    heat = _scale(recent["hot_days"].mean(), 0, 15)
    rain_cv = yt["rain_mm"].std() / yt["rain_mm"].mean()
    rain_var = _scale(rain_cv, 0, 0.3)
    trend = yt["soil_wetness"].iloc[-1] - yt["soil_wetness"].iloc[0]
    decline = _scale(-trend, 0, 0.1)

    ind = {
        "drought_risk": round(min(1.0, drought + drought_boost), 3),
        "heat_stress": round(min(1.0, heat + heat_boost), 3),
        "rain_variability": round(rain_var, 3),
        "moisture_decline": round(decline, 3),
    }
    if ndvi is not None and len(ndvi):
        ny = ndvi_yearly(ndvi)["summer_ndvi"]
        drop = ny.iloc[0] - ny.iloc[-1]          # first year minus last year
        ind["veg_decline"] = round(_scale(drop, 0, 0.1), 3)
    return ind

# ---------------- Rotation scoring ----------------
PRIORITY_PRESETS = {
    "Save water":   {"resilience": 8, "soil": 3, "yield": 3},
    "Improve soil": {"resilience": 3, "soil": 8, "yield": 3},
    "Max yield":    {"resilience": 3, "soil": 2, "yield": 8},
    "Balanced":     {"resilience": 5, "soil": 5, "yield": 5},
}

def _components(rot, ind):
    d, h = ind["drought_risk"], ind["heat_stress"]
    drought_fit = 0.5 * rot["drought_tolerance"] + 0.5 * (1 - rot["water_use"])
    heat_fit = rot["heat_tolerance"]
    resilience = (d * drought_fit + h * heat_fit) / (d + h) if (d + h) > 0 else 0.5
    # Soil: benefit counts more when moisture AND (if available) vegetation are declining
    soil_stress = ind["moisture_decline"]
    if "veg_decline" in ind:
        soil_stress = (ind["moisture_decline"] + ind["veg_decline"]) / 2
    soil = rot["soil_benefit"] * (0.5 + 0.5 * soil_stress)
    stress = max(d, h)
    yld = rot["yield_potential"] * (1 - stress * (1 - rot["drought_tolerance"]) * 0.6)
    return {"resilience": resilience, "soil": soil, "yield": yld}

def _reasons(rot, ind, comp):
    r = []
    if ind["drought_risk"] >= 0.5:
        r.append(f"Field was dry on ~{ind['drought_risk']*50:.0f}% of recent growing-season days; "
                 f"this rotation has {'strong' if rot['drought_tolerance']>=0.6 else 'weak'} drought tolerance")
    if ind["heat_stress"] >= 0.5:
        r.append(f"Frequent hot days (35°C+); heat tolerance is {'good' if rot['heat_tolerance']>=0.6 else 'limited'}")
    if ind["moisture_decline"] >= 0.5:
        r.append(f"Soil moisture is trending down; soil benefit is {'high' if rot['soil_benefit']>=0.7 else 'moderate'}")
    if ind.get("veg_decline", 0) >= 0.5:
        r.append("Satellite NDVI shows peak crop greenness declining; soil-building rotations help recovery")
    r.append(f"Water demand is {'low' if rot['water_use']<0.5 else 'moderate' if rot['water_use']<0.7 else 'high'}")
    return r

def score_rotations(indicators, priorities="Balanced"):
    """
    priorities: preset name (str) OR dict {"resilience":0-10,"soil":0-10,"yield":0-10}
    Returns list sorted best-first: [{"rotation","crops","score","components","reasons","note"}, ...]
    """
    w = PRIORITY_PRESETS[priorities] if isinstance(priorities, str) else priorities
    total_w = sum(w.values()) or 1
    results = []
    for rot in ROTATIONS:
        comp = _components(rot, indicators)
        score = sum(comp[k] * w[k] for k in w) / total_w * 100
        results.append({
            "rotation": rot["name"], "crops": rot["crops"],
            "score": round(score, 1),
            "components": {k: round(v * 100, 1) for k, v in comp.items()},
            "reasons": _reasons(rot, indicators, comp),
            "note": rot["note"],
        })
    return sorted(results, key=lambda x: x["score"], reverse=True)

if __name__ == "__main__":
    df = load_power()
    nd = load_ndvi()
    print(yearly_table(df))
    print(ndvi_yearly(nd))
    ind = compute_indicators(df, ndvi=nd)
    print(ind)
    for p in PRIORITY_PRESETS:
        print(p, [(r["rotation"][:20], r["score"]) for r in score_rotations(ind, p)])
# app.py -- Field Shift: click-to-pick location, NASA POWER (live) + MODIS NDVI (demo field)
import os
import folium
import pandas as pd
import plotly.express as px
import pycountry
import reverse_geocoder as rg
import streamlit as st
from streamlit_folium import st_folium
from fetch_data import fetch_power
from scoring import (load_power, load_ndvi, yearly_table,
                     compute_indicators, score_rotations, PRIORITY_PRESETS)

st.set_page_config(page_title="Field Shift", layout="wide")

GREEN = "#2E7D32"
DEMO = (42.03, -93.62)   # Ames, Iowa: has cached POWER + NDVI data
PLACES = {
    "Ames, Iowa, USA (demo)": DEMO,
    "Punjab, India": (30.90, 75.85),
    "Pampas, Argentina": (-34.60, -60.50),
    "Nile Delta, Egypt": (30.80, 31.00),
    "Riverina, Australia": (-35.00, 146.00),
    "Custom (clicked on map)": None,
}

# ---------- Styling ----------
st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 2.2rem; max-width: 1200px;}
h1 {font-weight: 700; letter-spacing: -0.5px; margin-bottom: 0;}
.subtitle {opacity: 0.7; margin: 0 0 1.2rem 0; font-size: 1.02rem;}
[data-testid="stMetric"] {
    background: rgba(46,125,50,0.07); border: 1px solid rgba(46,125,50,0.25);
    border-radius: 10px; padding: 14px 16px;
}
[data-testid="stMetricLabel"] p {font-size: 0.8rem; opacity: 0.75;}
.hero {
    background: rgba(46,125,50,0.10); border: 1px solid rgba(46,125,50,0.35);
    border-left: 6px solid #2E7D32; border-radius: 10px; padding: 18px 22px; margin: 6px 0 14px 0;
}
.hero .tag {font-size: 0.75rem; letter-spacing: 1px; text-transform: uppercase; opacity: 0.7;}
.hero .name {font-size: 1.5rem; font-weight: 700; margin: 2px 0;}
.hero .meta {opacity: 0.8; font-size: 0.95rem;}
.stTabs [data-baseweb="tab-list"] {gap: 6px;}
</style>
""", unsafe_allow_html=True)

def is_demo(lat, lon):
    return abs(lat - DEMO[0]) < 0.05 and abs(lon - DEMO[1]) < 0.05

# ---------- Session state ----------
st.session_state.setdefault("lat", DEMO[0])
st.session_state.setdefault("lon", DEMO[1])
st.session_state.setdefault("place", "Ames, Iowa, USA (demo)")
st.session_state.setdefault("last_click_seen", None)
if st.session_state.pop("clicked_flag", False):   # set by map click (before widgets are built)
    st.session_state["place"] = "Custom (clicked on map)"

def on_place_change():
    coords = PLACES[st.session_state["place"]]
    if coords:
        st.session_state["lat"], st.session_state["lon"] = coords

# ---------- Data loading ----------
@st.cache_data(show_spinner=False)
def _get_power(lat, lon):
    """Cached. Raises on failure so errors are NOT cached (retry works)."""
    if is_demo(lat, lon):
        return load_power("data/power_iowa.csv")
    path = f"data/cache_{lat:.2f}_{lon:.2f}.csv"
    fetched = not os.path.exists(path)
    df = fetch_power(lat, lon) if fetched else load_power(path)
    if df["GWETROOT"].isna().mean() > 0.5:
        raise ValueError("NASA POWER has no land data for this point (ocean?). Pick a point on land.")
    if fetched:
        df.to_csv(path)
    return df

def get_power(lat, lon):
    """Returns (DataFrame or None, error message or None)."""
    try:
        return _get_power(lat, lon), None
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Could not fetch NASA POWER data ({e}). Check your internet or pick another point."

@st.cache_data(show_spinner=False)
def describe_place(lat, lon):
    """Offline reverse geocoding: nearest city, region, country."""
    try:
        r = rg.search((lat, lon), mode=1)[0]
        country = pycountry.countries.get(alpha_2=r["cc"])
        parts = [r["name"], r["admin1"], country.name if country else r["cc"]]
        return "Near " + ", ".join(p for p in parts if p)
    except Exception:
        return "Custom location"

@st.cache_data
def get_ndvi():
    return load_ndvi("data/ndvi_iowa.csv")

def tidy(fig, title, height=280):
    fig.update_layout(title=dict(text=title, font=dict(size=14)), height=height,
                      margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
    return fig

# ---------- Sidebar ----------
st.sidebar.markdown("**Location**")
st.sidebar.selectbox("Location", list(PLACES), key="place", on_change=on_place_change,
                     label_visibility="collapsed")
st.sidebar.caption("Or click anywhere on the map.")

st.sidebar.markdown("**Priorities**")
mode = st.sidebar.radio("Priority mode", ["Quick preset", "Custom sliders"], horizontal=True,
                        label_visibility="collapsed")
if mode == "Quick preset":
    priorities = st.sidebar.selectbox("What matters most?", list(PRIORITY_PRESETS),
                                      label_visibility="collapsed")
else:
    priorities = {
        "resilience": st.sidebar.slider("Water & climate resilience", 0, 10, 5),
        "soil": st.sidebar.slider("Soil health", 0, 10, 5),
        "yield": st.sidebar.slider("Yield / income", 0, 10, 5),
    }

st.sidebar.markdown("**What-if scenario**")
drought_up = st.sidebar.slider("Extra drought risk (+%)", 0, 40, 0) / 100
heat_up = st.sidebar.slider("Extra heat stress (+%)", 0, 40, 0) / 100

# ---------- Header ----------
st.title("Field Shift")
st.markdown('<p class="subtitle">Crop-rotation decision support powered by NASA Earth observation data</p>',
            unsafe_allow_html=True)

lat, lon = round(st.session_state["lat"], 2), round(st.session_state["lon"], 2)
demo_field = is_demo(lat, lon)

# ---------- Map (full width, top) ----------
m = folium.Map(location=[lat, lon], zoom_start=5, tiles="OpenStreetMap")
folium.Marker([lat, lon], tooltip=f"Selected field ({lat}, {lon})",
              icon=folium.Icon(color="green", icon="leaf")).add_to(m)
out = st_folium(m, height=380, use_container_width=True, returned_objects=["last_clicked"])
click = out.get("last_clicked") if out else None
if click and click != st.session_state["last_click_seen"]:
    st.session_state["last_click_seen"] = click
    st.session_state["lat"] = round(click["lat"], 2)
    st.session_state["lon"] = round(click["lng"], 2)
    st.session_state["clicked_flag"] = True
    st.rerun()
st.caption("Click anywhere on the map to analyse another location.")

# ---------- Fetch data for the selected point ----------
with st.spinner("Fetching NASA POWER data for this location (first time can take ~10-30 s)..."):
    df, err = get_power(lat, lon)
if err:
    st.error(err)
    st.stop()

ndvi = get_ndvi() if demo_field else None
yt = yearly_table(df)

# ---------- Compute ----------
ind = compute_indicators(df, drought_boost=drought_up, heat_boost=heat_up, ndvi=ndvi)
results = score_rotations(ind, priorities)
best = results[0]

# ---------- Selected field + best fit (below the map) ----------
place_name = st.session_state["place"]
place_name = describe_place(lat, lon) if place_name.startswith("Custom") else place_name.replace(" (demo)", "")
info_l, info_r = st.columns(2, gap="large")
with info_l:
    st.markdown("**Selected field**")
    st.markdown(f"### {place_name}")
    st.caption(f"Lat {lat}, Lon {lon}  |  Data: NASA POWER" + (" + MODIS NDVI" if ndvi is not None else ""))
with info_r:
    st.markdown(
        f"""<div class="hero">
        <div class="tag">Best fit for your priorities</div>
        <div class="name">{best['rotation']}</div>
        <div class="meta">Score {best['score']} / 100<br>{best['note']}</div>
        </div>""", unsafe_allow_html=True)

if not demo_field:
    st.info("Outside the demo field: rotation traits are Iowa-style temperate crops and thresholds are "
            "tuned to Iowa, so treat results as a demo of the method. NDVI is loaded for the demo field only.")
if drought_up or heat_up:
    st.warning("What-if scenario is ON: conditions are worse than the historical record.")

# ---------- Key readings ----------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Drought risk", f"{ind['drought_risk']*100:.0f}%",
          help="Share of recent growing-season days (May-Sep) with dry root-zone soil.")
c2.metric("Heat stress", f"{ind['heat_stress']*100:.0f}%",
          help="Days per season at or above 35°C, scaled to 0-100%.")
c3.metric("Rain variability", f"{ind['rain_variability']*100:.0f}%",
          help="How much seasonal rainfall swings from year to year.")
c4.metric("Soil moisture decline", f"{ind['moisture_decline']*100:.0f}%",
          help="Drop in growing-season soil wetness from the first to the last year.")
c5.metric("Greenness decline", f"{ind['veg_decline']*100:.0f}%" if "veg_decline" in ind else "n/a",
          help="Drop in peak-summer MODIS NDVI (crop greenness). Demo field only.")

st.write("")
tab_rec, tab_evidence, tab_compare, tab_about = st.tabs(
    ["Recommendations", "Climate evidence", "Compare", "About"])

# ---------- Tab 1: Recommendations ----------
with tab_rec:
    score_df = pd.DataFrame({"Rotation": [r["rotation"] for r in results],
                             "Score": [r["score"] for r in results]}).iloc[::-1]
    fig = px.bar(score_df, x="Score", y="Rotation", orientation="h", range_x=[0, 100])
    fig.update_traces(marker_color=GREEN)
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), yaxis_title=None)
    st.plotly_chart(fig)

    for i, r in enumerate(results, start=1):
        with st.expander(f"#{i}  {r['rotation']}  |  {r['score']} / 100", expanded=(i == 1)):
            a, b, c = st.columns(3)
            a.metric("Resilience", f"{r['components']['resilience']:.0f}")
            b.metric("Soil health", f"{r['components']['soil']:.0f}")
            c.metric("Yield", f"{r['components']['yield']:.0f}")
            st.markdown("**Why this ranking**")
            for reason in r["reasons"]:
                st.write(f"- {reason}")

# ---------- Tab 2: Climate evidence ----------
with tab_evidence:
    yt_plot = yt.reset_index().rename(columns={"date": "Year"})
    yt_plot["Year"] = yt_plot["Year"].astype(str)
    chart_l, chart_r = st.columns(2)
    with chart_l:
        f1 = px.bar(yt_plot, x="Year", y="rain_mm", labels={"rain_mm": "mm"})
        f1.update_traces(marker_color=GREEN)
        st.plotly_chart(tidy(f1, "Growing-season rain (May-Sep)"))
        f3 = px.bar(yt_plot, x="Year", y="hot_days", labels={"hot_days": "days"})
        f3.update_traces(marker_color=GREEN)
        st.plotly_chart(tidy(f3, "Hot days (35°C or higher)"))
    with chart_r:
        f2 = px.line(yt_plot, x="Year", y="soil_wetness", markers=True, labels={"soil_wetness": "0-1"})
        f2.update_traces(line_color=GREEN, marker_color=GREEN)
        st.plotly_chart(tidy(f2, "Root-zone soil wetness"))
        if ndvi is not None:
            f4 = px.line(ndvi.reset_index(), x="date", y="ndvi", labels={"ndvi": "NDVI", "date": ""})
            f4.update_traces(line_color=GREEN)
            st.plotly_chart(tidy(f4, "Crop greenness (MODIS NDVI)"))
        else:
            st.info("NDVI is loaded for the demo field only (exported from NASA AppEEARS).")

# ---------- Tab 3: Compare ----------
with tab_compare:
    names = [r["rotation"] for r in results]
    pick = st.multiselect("Pick 2 rotations to compare", names, default=names[:2], max_selections=2)
    if len(pick) == 2:
        rows = []
        for r in results:
            if r["rotation"] in pick:
                for k, v in r["components"].items():
                    rows.append({"Rotation": r["rotation"], "Factor": k.capitalize(), "Score": v})
        fig = px.bar(pd.DataFrame(rows), x="Factor", y="Score", color="Rotation", barmode="group",
                     color_discrete_sequence=[GREEN, "#90A4AE"], range_y=[0, 100])
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig)
    else:
        st.caption("Select exactly two rotations.")

# ---------- Tab 4: About ----------
with tab_about:
    st.markdown("""
**Data**
- **NASA POWER**: daily rainfall, maximum temperature and root-zone soil wetness (2019-2023), fetched live for any land point.
- **MODIS MOD13Q1 NDVI** (via NASA AppEEARS): crop greenness, loaded for the demo field.

**Method**
- Raw NASA series become 0-100% stress indicators (drought, heat, rain variability, moisture and greenness decline).
- Each rotation is scored on resilience, soil health and yield, then combined using the farmer's priority weights.
- The model is rule-based and transparent, so every ranking comes with reasons. Nothing is trained.

**Limitations**
- Rotation traits are agronomic estimates and thresholds are tuned to Iowa.
- NDVI covers the demo field only; POWER is a gridded, coarse-resolution product.
""")
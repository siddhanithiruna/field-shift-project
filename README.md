# Field Shift
### 🚀 [Click here to view the Live App] (https://field-shift-project-xrdzg2lvna6kdoawkcjx4h.streamlit.app/)

Crop-rotation decision-support tool built on NASA Earth observation data
(2026 NASA Space Apps Challenge: "Field Shift: Adapting Farms with NASA Data").

## Run it
    python -m venv venv
    venv\Scripts\activate        # Mac/Linux: source venv/bin/activate
    pip install -r requirements.txt
    streamlit run app.py

## Data
- NASA POWER: rainfall, max temperature, root-zone soil wetness (fetched live for any land point)
- MODIS MOD13Q1 NDVI via NASA AppEEARS (demo field: Ames, Iowa)

## Method
Rule-based, transparent multi-criteria scoring: NASA series become stress indicators,
which are matched against rotation traits and weighted by farmer priorities.

## Limitations
Rotation traits are agronomic estimates tuned to Iowa; NDVI is loaded for the demo field only.
  
## SI Use
Code ideas were developed with assistance from Claude (Anthropic). Reviewed, tested and integrated by our team.

## Team Members
- Siddhani A/P Thirunavukkarasu
- Siew Jin You
- Rangitha A/P Suresh

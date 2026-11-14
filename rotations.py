# rotations.py
# Traits are 0-1 (higher = more of that trait). Edit freely.
#   water_use         : how thirsty the rotation is (high = bad in drought)
#   drought_tolerance : how well it handles dry spells
#   heat_tolerance    : how well it handles hot days
#   soil_benefit      : erosion control, organic matter, nitrogen fixing
#   yield_potential   : relative profit/yield in normal conditions

ROTATIONS = [
    {
        "name": "Corn → Soybean",
        "crops": ["Corn", "Soybean"],
        "water_use": 0.85,
        "drought_tolerance": 0.35,
        "heat_tolerance": 0.40,
        "soil_benefit": 0.50,
        "yield_potential": 0.90,
        "note": "Standard Iowa rotation. High yield, but thirsty and drought-sensitive.",
    },
    {
        "name": "Corn → Soybean → Wheat + Cover Crop",
        "crops": ["Corn", "Soybean", "Wheat", "Cover crop"],
        "water_use": 0.65,
        "drought_tolerance": 0.55,
        "heat_tolerance": 0.55,
        "soil_benefit": 0.90,
        "yield_potential": 0.70,
        "note": "Longer rotation with cover crop. Best for soil health and erosion.",
    },
    {
        "name": "Soybean → Sorghum",
        "crops": ["Soybean", "Sorghum"],
        "water_use": 0.45,
        "drought_tolerance": 0.80,
        "heat_tolerance": 0.80,
        "soil_benefit": 0.60,
        "yield_potential": 0.60,
        "note": "Sorghum handles heat and drought well. Lower water demand.",
    },
    {
        "name": "Oats → Alfalfa → Corn",
        "crops": ["Oats", "Alfalfa", "Corn"],
        "water_use": 0.55,
        "drought_tolerance": 0.65,
        "heat_tolerance": 0.60,
        "soil_benefit": 0.95,
        "yield_potential": 0.65,
        "note": "Alfalfa fixes nitrogen and builds soil. Deep roots reach water.",
    },
]
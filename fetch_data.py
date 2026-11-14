import requests
import pandas as pd

LAT, LON = 42.03, -93.62          # Ames, Iowa (default demo region)
START, END = "20190101", "20231231"

PARAMS = [
    "PRECTOTCORR",         # rainfall (mm/day)
    "T2M",                 # avg temp (°C)
    "T2M_MAX",             # max temp (°C)
    "ALLSKY_SFC_SW_DWN",   # solar radiation
    "GWETROOT",            # root-zone soil wetness (0-1)
    "GWETTOP",             # surface soil wetness (0-1)
]

def fetch_power(lat=LAT, lon=LON, start=START, end=END):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()["properties"]["parameter"]

    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.apply(pd.to_numeric, errors="coerce")   
    df = df.mask(df == -999)                        
    return df

if __name__ == "__main__":
    df = fetch_power()
    df.to_csv("data/power_iowa.csv")
    print(df.head())
    print(f"Saved {len(df)} rows to data/power_iowa.csv")
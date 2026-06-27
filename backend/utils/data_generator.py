"""
AQI & Weather Data Generator / Simulator for Indian Cities
In production: replace simulate_* with real API calls (CPCB, OpenWeatherMap, IQAir)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import math

# -----------------------------------------------------------------
# AQI Category helpers
# -----------------------------------------------------------------
AQI_CATEGORIES = [
    (0,   50,  "Good",         "#00e400"),
    (51,  100, "Satisfactory", "#ffff00"),
    (101, 200, "Moderate",     "#ff7e00"),
    (201, 300, "Poor",         "#ff0000"),
    (301, 400, "Very Poor",    "#8f3f97"),
    (401, 500, "Severe",       "#7e0023"),
]

def get_aqi_category(aqi: int) -> dict:
    for lo, hi, name, color in AQI_CATEGORIES:
        if lo <= aqi <= hi:
            return {"category": name, "color": color}
    return {"category": "Severe", "color": "#7e0023"}


# -----------------------------------------------------------------
# City baseline profiles (realistic annual mean AQI for Indian cities)
# -----------------------------------------------------------------
CITY_PROFILES = {
    "Delhi":          {"base_aqi": 180, "volatility": 80, "seasonal_amp": 120},
    "Mumbai":         {"base_aqi": 100, "volatility": 40, "seasonal_amp": 60},
    "Kolkata":        {"base_aqi": 130, "volatility": 50, "seasonal_amp": 80},
    "Chennai":        {"base_aqi": 80,  "volatility": 30, "seasonal_amp": 40},
    "Bangalore":      {"base_aqi": 70,  "volatility": 25, "seasonal_amp": 30},
    "Hyderabad":      {"base_aqi": 90,  "volatility": 35, "seasonal_amp": 50},
    "Ahmedabad":      {"base_aqi": 140, "volatility": 55, "seasonal_amp": 70},
    "Pune":           {"base_aqi": 85,  "volatility": 30, "seasonal_amp": 45},
    "Jaipur":         {"base_aqi": 150, "volatility": 60, "seasonal_amp": 90},
    "Lucknow":        {"base_aqi": 160, "volatility": 65, "seasonal_amp": 100},
    "Kanpur":         {"base_aqi": 170, "volatility": 70, "seasonal_amp": 110},
    "Nagpur":         {"base_aqi": 120, "volatility": 45, "seasonal_amp": 65},
    "Indore":         {"base_aqi": 115, "volatility": 40, "seasonal_amp": 60},
    "Bhopal":         {"base_aqi": 110, "volatility": 40, "seasonal_amp": 55},
    "Patna":          {"base_aqi": 165, "volatility": 70, "seasonal_amp": 105},
    "Varanasi":       {"base_aqi": 155, "volatility": 65, "seasonal_amp": 95},
    "Agra":           {"base_aqi": 145, "volatility": 60, "seasonal_amp": 85},
    "Surat":          {"base_aqi": 105, "volatility": 38, "seasonal_amp": 55},
    "Coimbatore":     {"base_aqi": 65,  "volatility": 22, "seasonal_amp": 28},
    "Visakhapatnam":  {"base_aqi": 75,  "volatility": 28, "seasonal_amp": 35},
}


def seasonal_factor(dt: datetime, amplitude: float) -> float:
    """Higher AQI in winter (Oct-Feb), lower in monsoon (Jun-Sep)."""
    day_of_year = dt.timetuple().tm_yday
    # Peak around day 330 (late Nov), trough around day 210 (late Jul)
    return amplitude * math.sin(2 * math.pi * (day_of_year - 210) / 365)


def diurnal_factor(dt: datetime) -> float:
    """AQI peaks in morning rush (8-10am) and evening (7-9pm)."""
    hour = dt.hour
    morning = 20 * math.exp(-0.5 * ((hour - 9) / 2) ** 2)
    evening = 15 * math.exp(-0.5 * ((hour - 20) / 2) ** 2)
    return morning + evening


def generate_historical_aqi(city_name: str, days: int = 365) -> pd.DataFrame:
    """Generate realistic hourly AQI + pollutant data for a city."""
    profile = CITY_PROFILES.get(city_name, {"base_aqi": 120, "volatility": 45, "seasonal_amp": 60})
    records = []
    rng = np.random.default_rng(abs(hash(city_name)) % (2**31))

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    aqi_val = float(profile["base_aqi"])
    for i in range(days * 24):
        dt = start + timedelta(hours=i)
        target = (profile["base_aqi"]
                  + seasonal_factor(dt, profile["seasonal_amp"])
                  + diurnal_factor(dt))
        # AR(1) dynamics
        aqi_val = 0.85 * aqi_val + 0.15 * target + rng.normal(0, profile["volatility"] * 0.3)
        aqi_val = float(np.clip(aqi_val, 10, 500))
        aqi_int = int(round(aqi_val))

        # Derive pollutants proportionally
        pm25 = round(aqi_val * 0.45 + rng.normal(0, 5), 2)
        pm10 = round(aqi_val * 0.80 + rng.normal(0, 8), 2)
        no2  = round(aqi_val * 0.20 + rng.normal(0, 4), 2)
        so2  = round(aqi_val * 0.10 + rng.normal(0, 2), 2)
        co   = round(aqi_val * 0.05 + rng.normal(0, 1), 2)
        o3   = round(max(0, 40 - aqi_val * 0.05 + rng.normal(0, 5)), 2)
        nh3  = round(aqi_val * 0.03 + rng.normal(0, 1), 2)

        cat = get_aqi_category(aqi_int)["category"]
        records.append({
            "recorded_at": dt,
            "aqi": aqi_int,
            "category": cat,
            "pm25": max(0, pm25),
            "pm10": max(0, pm10),
            "no2":  max(0, no2),
            "so2":  max(0, so2),
            "co":   max(0, co),
            "o3":   max(0, o3),
            "nh3":  max(0, nh3),
        })

    return pd.DataFrame(records)


def generate_historical_weather(city_name: str, days: int = 365) -> pd.DataFrame:
    """Generate realistic hourly weather data for a city."""
    WEATHER_PROFILES = {
        "Delhi":    {"temp_mean": 25, "temp_amp": 15, "humidity": 55},
        "Mumbai":   {"temp_mean": 27, "temp_amp": 5,  "humidity": 75},
        "Kolkata":  {"temp_mean": 26, "temp_amp": 8,  "humidity": 72},
        "Chennai":  {"temp_mean": 28, "temp_amp": 4,  "humidity": 70},
        "Bangalore":{"temp_mean": 23, "temp_amp": 5,  "humidity": 62},
        "default":  {"temp_mean": 26, "temp_amp": 10, "humidity": 60},
    }
    wp = WEATHER_PROFILES.get(city_name, WEATHER_PROFILES["default"])
    records = []
    rng = np.random.default_rng((abs(hash(city_name)) + 1) % (2**31))

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    for i in range(days * 24):
        dt = start + timedelta(hours=i)
        doy = dt.timetuple().tm_yday
        hour = dt.hour

        # Temperature: seasonal + diurnal
        temp = (wp["temp_mean"]
                + wp["temp_amp"] * math.sin(2 * math.pi * (doy - 80) / 365)
                + 4 * math.sin(2 * math.pi * (hour - 14) / 24)
                + rng.normal(0, 1.5))

        humidity = wp["humidity"] + rng.normal(0, 8)
        humidity = float(np.clip(humidity, 10, 98))

        wind_speed = abs(rng.normal(3, 2))
        wind_dir   = int(rng.integers(0, 360))
        pressure   = round(1013 + rng.normal(0, 5), 2)
        visibility = round(float(np.clip(rng.normal(8, 3), 0.5, 20)), 2)
        dew_point  = round(temp - (100 - humidity) / 5, 2)
        cloud_cover= int(np.clip(rng.normal(30, 25), 0, 100))
        rainfall   = max(0, round(rng.normal(0, 0.5) if doy not in range(150, 270) else rng.normal(1, 2), 2))

        records.append({
            "recorded_at":  dt,
            "temperature":  round(temp, 2),
            "humidity":     round(humidity, 2),
            "wind_speed":   round(wind_speed, 2),
            "wind_direction": wind_dir,
            "pressure":     pressure,
            "visibility":   visibility,
            "dew_point":    dew_point,
            "cloud_cover":  cloud_cover,
            "rainfall":     rainfall,
        })

    return pd.DataFrame(records)


def generate_all_cities(days: int = 365):
    """Generator: yields (city_name, aqi_df, weather_df) for each city."""
    for city in CITY_PROFILES:
        yield city, generate_historical_aqi(city, days), generate_historical_weather(city, days)

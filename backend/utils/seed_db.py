"""
Seed the MySQL database with cities + 30 days of hourly AQI/weather data.
Usage:
    python seed_db.py                   # uses .env DB config
    python seed_db.py --days 90         # seed 90 days of data
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from backend.models.db_models import City, AQIReading, WeatherReading, get_engine, init_db
from backend.utils.data_generator import generate_all_cities, CITY_PROFILES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:password@localhost:3306/aqi_forecaster"
)

# City metadata (lat/lon/state/population)
CITY_META = {
    "Delhi":          {"state": "Delhi",          "lat": 28.6139, "lon": 77.2090, "pop": 32941000},
    "Mumbai":         {"state": "Maharashtra",    "lat": 19.0760, "lon": 72.8777, "pop": 20667656},
    "Kolkata":        {"state": "West Bengal",    "lat": 22.5726, "lon": 88.3639, "pop": 14850000},
    "Chennai":        {"state": "Tamil Nadu",     "lat": 13.0827, "lon": 80.2707, "pop": 10971108},
    "Bangalore":      {"state": "Karnataka",      "lat": 12.9716, "lon": 77.5946, "pop": 12765000},
    "Hyderabad":      {"state": "Telangana",      "lat": 17.3850, "lon": 78.4867, "pop": 10534418},
    "Ahmedabad":      {"state": "Gujarat",        "lat": 23.0225, "lon": 72.5714, "pop": 8059441},
    "Pune":           {"state": "Maharashtra",    "lat": 18.5204, "lon": 73.8567, "pop": 7276000},
    "Jaipur":         {"state": "Rajasthan",      "lat": 26.9124, "lon": 75.7873, "pop": 3073350},
    "Lucknow":        {"state": "Uttar Pradesh",  "lat": 26.8467, "lon": 80.9462, "pop": 3382900},
    "Kanpur":         {"state": "Uttar Pradesh",  "lat": 26.4499, "lon": 80.3319, "pop": 3020243},
    "Nagpur":         {"state": "Maharashtra",    "lat": 21.1458, "lon": 79.0882, "pop": 2742000},
    "Indore":         {"state": "Madhya Pradesh", "lat": 22.7196, "lon": 75.8577, "pop": 3239000},
    "Bhopal":         {"state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126, "pop": 2368145},
    "Patna":          {"state": "Bihar",          "lat": 25.5941, "lon": 85.1376, "pop": 2290419},
    "Varanasi":       {"state": "Uttar Pradesh",  "lat": 25.3176, "lon": 82.9739, "pop": 1432280},
    "Agra":           {"state": "Uttar Pradesh",  "lat": 27.1767, "lon": 78.0081, "pop": 1760285},
    "Surat":          {"state": "Gujarat",        "lat": 21.1702, "lon": 72.8311, "pop": 6584890},
    "Coimbatore":     {"state": "Tamil Nadu",     "lat": 11.0168, "lon": 76.9558, "pop": 2136916},
    "Visakhapatnam":  {"state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185, "pop": 2035922},
}


def seed(days: int = 30):
    engine = get_engine(DB_URL)
    init_db(engine)

    with Session(engine) as session:
        # Insert cities
        city_map = {}
        for name, meta in CITY_META.items():
            existing = session.query(City).filter_by(name=name).first()
            if existing:
                city_map[name] = existing.id
                continue
            c = City(
                name=name, state=meta["state"],
                latitude=meta["lat"], longitude=meta["lon"],
                population=meta["pop"]
            )
            session.add(c)
            session.flush()
            city_map[name] = c.id
        session.commit()
        log.info(f"✅ {len(city_map)} cities ready")

        # Insert AQI + weather readings
        for city_name, aqi_df, weather_df in generate_all_cities(days=days):
            cid = city_map.get(city_name)
            if cid is None:
                continue

            # Delete existing to avoid duplicates
            session.query(AQIReading).filter_by(city_id=cid).delete()
            session.query(WeatherReading).filter_by(city_id=cid).delete()

            aqi_records = [
                AQIReading(
                    city_id=cid,
                    recorded_at=row.recorded_at,
                    aqi=int(row.aqi),
                    category=row.category,
                    pm25=float(row.pm25),
                    pm10=float(row.pm10),
                    no2=float(row.no2),
                    so2=float(row.so2),
                    co=float(row.co),
                    o3=float(row.o3),
                    nh3=float(row.nh3),
                )
                for _, row in aqi_df.iterrows()
            ]
            weather_records = [
                WeatherReading(
                    city_id=cid,
                    recorded_at=row.recorded_at,
                    temperature=float(row.temperature),
                    humidity=float(row.humidity),
                    wind_speed=float(row.wind_speed),
                    wind_direction=int(row.wind_direction),
                    pressure=float(row.pressure),
                    visibility=float(row.visibility),
                    dew_point=float(row.dew_point),
                    cloud_cover=int(row.cloud_cover),
                    rainfall=float(row.rainfall),
                )
                for _, row in weather_df.iterrows()
            ]
            session.bulk_save_objects(aqi_records)
            session.bulk_save_objects(weather_records)
            session.commit()
            log.info(f"  {city_name}: {len(aqi_records)} AQI + {len(weather_records)} weather records")

    log.info("✅ Database seeding complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    seed(days=args.days)

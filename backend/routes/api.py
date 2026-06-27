"""
REST API Routes for AQI Forecaster
"""
import json
import logging
from datetime import datetime, timedelta, date
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.models.db_models import City, AQIReading, WeatherReading, AQIForecast, get_engine
from backend.utils.data_generator import get_aqi_category, CITY_PROFILES, generate_historical_aqi, generate_historical_weather
from backend.ml.forecaster import make_features, forecast_city

log = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")


def get_session():
    engine = get_engine(current_app.config["DATABASE_URL"])
    return Session(engine)


# ── Helpers ───────────────────────────────────────────

def _current_aqi_all_cities():
    """Return current simulated AQI for all cities (for map display)."""
    results = []
    from backend.utils.data_generator import CITY_PROFILES
    
    # Use data generator for live-ish values
    now = datetime.now()
    import math, numpy as np
    
    # City lat/lon map
    CITY_COORDS = {
        "Delhi": (28.6139, 77.2090), "Mumbai": (19.0760, 72.8777),
        "Kolkata": (22.5726, 88.3639), "Chennai": (13.0827, 80.2707),
        "Bangalore": (12.9716, 77.5946), "Hyderabad": (17.3850, 78.4867),
        "Ahmedabad": (23.0225, 72.5714), "Pune": (18.5204, 73.8567),
        "Jaipur": (26.9124, 75.7873), "Lucknow": (26.8467, 80.9462),
        "Kanpur": (26.4499, 80.3319), "Nagpur": (21.1458, 79.0882),
        "Indore": (22.7196, 75.8577), "Bhopal": (23.2599, 77.4126),
        "Patna": (25.5941, 85.1376), "Varanasi": (25.3176, 82.9739),
        "Agra": (27.1767, 78.0081), "Surat": (21.1702, 72.8311),
        "Coimbatore": (11.0168, 76.9558), "Visakhapatnam": (17.6868, 83.2185),
    }
    CITY_STATES = {
        "Delhi": "Delhi", "Mumbai": "Maharashtra", "Kolkata": "West Bengal",
        "Chennai": "Tamil Nadu", "Bangalore": "Karnataka", "Hyderabad": "Telangana",
        "Ahmedabad": "Gujarat", "Pune": "Maharashtra", "Jaipur": "Rajasthan",
        "Lucknow": "Uttar Pradesh", "Kanpur": "Uttar Pradesh", "Nagpur": "Maharashtra",
        "Indore": "Madhya Pradesh", "Bhopal": "Madhya Pradesh", "Patna": "Bihar",
        "Varanasi": "Uttar Pradesh", "Agra": "Uttar Pradesh", "Surat": "Gujarat",
        "Coimbatore": "Tamil Nadu", "Visakhapatnam": "Andhra Pradesh",
    }

    rng = np.random.default_rng(int(now.strftime("%Y%m%d%H")))
    for city, profile in CITY_PROFILES.items():
        doy = now.timetuple().tm_yday
        hour = now.hour
        # Seasonal: winter high, monsoon low
        seasonal = profile["seasonal_amp"] * math.sin(2 * math.pi * (doy - 210) / 365)
        # Diurnal: morning rush (8-10am) + evening peak (7-9pm)
        diurnal = (15 * math.exp(-0.5 * ((hour - 9) / 2) ** 2) +
                   12 * math.exp(-0.5 * ((hour - 20) / 2) ** 2))
        # Always stay close to city baseline — small noise only
        raw = profile["base_aqi"] + seasonal + diurnal + rng.normal(0, profile["volatility"] * 0.15)
        aqi = int(np.clip(raw, max(30, profile["base_aqi"] * 0.4), 500))
        cat = get_aqi_category(aqi)
        lat, lon = CITY_COORDS.get(city, (20.0, 78.0))
        results.append({
            "city": city,
            "state": CITY_STATES.get(city, ""),
            "latitude": lat,
            "longitude": lon,
            "aqi": aqi,
            "category": cat["category"],
            "color": cat["color"],
            "timestamp": now.isoformat(),
        })
    return results


# ── Endpoints ─────────────────────────────────────────

@api.route("/cities", methods=["GET"])
def get_cities():
    """List all cities with current AQI."""
    try:
        data = _current_aqi_all_cities()
        return jsonify({"success": True, "data": data, "count": len(data)})
    except Exception as e:
        log.error(e)
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/city/<city_name>/current", methods=["GET"])
def get_city_current(city_name: str):
    """Current AQI + weather snapshot for a city."""
    try:
        # Use 7 days and take last 24h mean to get stable realistic value
        aqi_df = generate_historical_aqi(city_name, days=7)
        wx_df  = generate_historical_weather(city_name, days=7)

        # Last 24 hours mean AQI — avoids single-hour spikes/dips
        last_24h = aqi_df.tail(24)
        mean_aqi = int(last_24h["aqi"].mean())
        latest_aqi = last_24h.iloc[-1].copy()
        latest_aqi["aqi"] = mean_aqi
        # Scale pollutants to match mean AQI
        scale = mean_aqi / max(float(aqi_df.iloc[-1]["aqi"]), 1)
        for pol in ["pm25","pm10","no2","so2","co","o3"]:
            latest_aqi[pol] = latest_aqi[pol] * scale

        latest_wx  = wx_df.iloc[-1]
        cat = get_aqi_category(int(latest_aqi["aqi"]))

        return jsonify({
            "success": True,
            "city": city_name,
            "aqi": {
                "value":    int(latest_aqi["aqi"]),
                "category": cat["category"],
                "color":    cat["color"],
                "pm25":  round(float(latest_aqi["pm25"]), 2),
                "pm10":  round(float(latest_aqi["pm10"]), 2),
                "no2":   round(float(latest_aqi["no2"]), 2),
                "so2":   round(float(latest_aqi["so2"]), 2),
                "co":    round(float(latest_aqi["co"]), 2),
                "o3":    round(float(latest_aqi["o3"]), 2),
            },
            "weather": {
                "temperature":  round(float(latest_wx["temperature"]), 1),
                "humidity":     round(float(latest_wx["humidity"]), 1),
                "wind_speed":   round(float(latest_wx["wind_speed"]), 1),
                "wind_direction": int(latest_wx["wind_direction"]),
                "pressure":     round(float(latest_wx["pressure"]), 1),
                "visibility":   round(float(latest_wx["visibility"]), 1),
            },
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        log.error(e)
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/city/<city_name>/history", methods=["GET"])
def get_city_history(city_name: str):
    """7-day hourly AQI history for a city (daily aggregated)."""
    days = int(request.args.get("days", 30))
    try:
        aqi_df = generate_historical_aqi(city_name, days=days)
        aqi_df["date"] = aqi_df["recorded_at"].dt.date.astype(str)
        daily = aqi_df.groupby("date").agg(
            aqi_mean=("aqi", "mean"),
            aqi_max=("aqi", "max"),
            aqi_min=("aqi", "min"),
            pm25=("pm25", "mean"),
            pm10=("pm10", "mean"),
        ).reset_index()

        records = []
        for _, row in daily.iterrows():
            cat = get_aqi_category(int(row["aqi_mean"]))
            records.append({
                "date":     row["date"],
                "aqi":      round(float(row["aqi_mean"]), 1),
                "aqi_max":  round(float(row["aqi_max"]), 1),
                "aqi_min":  round(float(row["aqi_min"]), 1),
                "category": cat["category"],
                "color":    cat["color"],
                "pm25":     round(float(row["pm25"]), 2),
                "pm10":     round(float(row["pm10"]), 2),
            })

        return jsonify({"success": True, "city": city_name, "days": days, "data": records})
    except Exception as e:
        log.error(e)
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/city/<city_name>/forecast", methods=["GET"])
def get_city_forecast(city_name: str):
    """7-day AQI forecast using the trained ML model."""
    horizon = int(request.args.get("days", 7))
    try:
        forecasts = forecast_city(city_name, horizon=horizon)
        return jsonify({
            "success":  True,
            "city":     city_name,
            "horizon":  horizon,
            "model":    "RF+GB Ensemble",
            "forecasts":forecasts,
        })
    except FileNotFoundError:
        # Model not trained yet – return simulated forecast
        import numpy as np
        profile = CITY_PROFILES.get(city_name, {"base_aqi": 120, "volatility": 40, "seasonal_amp": 60})
        rng = np.random.default_rng(42)
        forecasts = []
        base = profile["base_aqi"]
        for i in range(1, horizon + 1):
            pred = int(np.clip(base + rng.normal(0, profile["volatility"] * 0.4), 10, 500))
            cat = get_aqi_category(pred)
            forecasts.append({
                "date": (datetime.now().date() + timedelta(days=i)).isoformat(),
                "predicted_aqi": pred,
                "category": cat["category"],
                "color": cat["color"],
                "confidence_lower": max(0, pred - 25),
                "confidence_upper": min(500, pred + 25),
            })
        return jsonify({
            "success": True, "city": city_name, "horizon": horizon,
            "model": "Simulated (train model first)",
            "forecasts": forecasts,
        })
    except Exception as e:
        log.error(e)
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/city/<city_name>/pollutants", methods=["GET"])
def get_city_pollutants(city_name: str):
    """Last 7 days of daily mean pollutant breakdown."""
    try:
        aqi_df = generate_historical_aqi(city_name, days=7)
        aqi_df["date"] = aqi_df["recorded_at"].dt.date.astype(str)
        daily = aqi_df.groupby("date").agg(
            pm25=("pm25","mean"), pm10=("pm10","mean"), no2=("no2","mean"),
            so2=("so2","mean"), co=("co","mean"), o3=("o3","mean"), nh3=("nh3","mean")
        ).reset_index()
        return jsonify({"success": True, "city": city_name, "data": daily.round(2).to_dict(orient="records")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/compare", methods=["GET"])
def compare_cities():
    """Compare current AQI across multiple cities."""
    cities_param = request.args.get("cities", "")
    cities = [c.strip() for c in cities_param.split(",") if c.strip()]
    if not cities:
        cities = list(CITY_PROFILES.keys())[:8]

    results = []
    for city in cities:
        aqi_df = generate_historical_aqi(city, days=1)
        latest = aqi_df.iloc[-1]
        cat = get_aqi_category(int(latest["aqi"]))
        results.append({
            "city": city, "aqi": int(latest["aqi"]),
            "category": cat["category"], "color": cat["color"],
        })

    results.sort(key=lambda x: x["aqi"], reverse=True)
    return jsonify({"success": True, "data": results})


@api.route("/stats/summary", methods=["GET"])
def get_summary_stats():
    """National AQI summary statistics."""
    all_cities = _current_aqi_all_cities()
    aqis = [c["aqi"] for c in all_cities]
    
    import numpy as np
    cat_counts = {}
    for c in all_cities:
        cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1

    return jsonify({
        "success": True,
        "total_cities": len(all_cities),
        "national_avg_aqi": round(float(np.mean(aqis)), 1),
        "worst_city": max(all_cities, key=lambda x: x["aqi"]),
        "best_city":  min(all_cities, key=lambda x: x["aqi"]),
        "category_distribution": cat_counts,
        "timestamp": datetime.now().isoformat(),
    })


@api.route("/train", methods=["POST"])
def train_models():
    """Trigger model training for all cities (background task)."""
    import threading
    def _train():
        from backend.utils.data_generator import generate_all_cities
        from backend.ml.forecaster import make_features, train_city_model
        for city_name, aqi_df, weather_df in generate_all_cities(days=365):
            try:
                df = make_features(aqi_df, weather_df)
                train_city_model(city_name, df)
                log.info(f"Trained model for {city_name}")
            except Exception as e:
                log.error(f"Error training {city_name}: {e}")

    t = threading.Thread(target=_train, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Training started in background. Check /api/models for status."})


@api.route("/models", methods=["GET"])
def get_model_status():
    """List which city models are trained."""
    models_dir = Path(__file__).parent.parent.parent / "models"
    trained = []
    for pkl in models_dir.glob("*_model.pkl"):
        city = pkl.stem.replace("_model", "").replace("_", " ").title()
        stat = pkl.stat()
        trained.append({
            "city":       city,
            "model_file": pkl.name,
            "size_kb":    round(stat.st_size / 1024, 1),
            "trained_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

    # Load summary if available
    summary_path = models_dir / "training_summary.json"
    summary = []
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)

    return jsonify({
        "success": True,
        "trained_models": len(trained),
        "models": trained,
        "metrics": summary,
    })

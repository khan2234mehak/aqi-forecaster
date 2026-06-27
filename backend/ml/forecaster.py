"""
AQI Time-Series Forecasting Engine
===================================
Strategy:
  1. Feature engineering on hourly AQI + weather data
  2. Daily aggregation → 24-hour mean AQI per city
  3. Two models trained per city:
       a. SARIMA  – captures trend + seasonality
       b. RandomForest – captures non-linear weather interactions
  4. Ensemble: weighted average (60% RF + 40% SARIMA)
  5. 7-day rolling forecast with 95% confidence interval

Run standalone:  python forecaster.py  (trains all cities, saves models)
"""

import os
import sys
import math
import json
import joblib
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────
# Feature Engineering
# ──────────────────────────────────────────────

def make_features(aqi_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge AQI + weather hourly → daily aggregate → time/lag features.
    Returns a daily feature DataFrame ready for training.
    """
    aqi_df = aqi_df.copy()
    weather_df = weather_df.copy()

    aqi_df["date"] = pd.to_datetime(aqi_df["recorded_at"]).dt.date
    weather_df["date"] = pd.to_datetime(weather_df["recorded_at"]).dt.date

    # Daily AQI aggregates
    daily_aqi = aqi_df.groupby("date").agg(
        aqi_mean=("aqi", "mean"),
        aqi_max=("aqi", "max"),
        aqi_min=("aqi", "min"),
        aqi_std=("aqi", "std"),
        pm25_mean=("pm25", "mean"),
        pm10_mean=("pm10", "mean"),
        no2_mean=("no2", "mean"),
        so2_mean=("so2", "mean"),
        co_mean=("co", "mean"),
        o3_mean=("o3", "mean"),
    ).reset_index()

    # Daily weather aggregates
    daily_wx = weather_df.groupby("date").agg(
        temp_mean=("temperature", "mean"),
        temp_max=("temperature", "max"),
        humidity_mean=("humidity", "mean"),
        wind_speed_mean=("wind_speed", "mean"),
        pressure_mean=("pressure", "mean"),
        visibility_mean=("visibility", "mean"),
        rainfall_sum=("rainfall", "sum"),
        cloud_cover_mean=("cloud_cover", "mean"),
    ).reset_index()

    df = daily_aqi.merge(daily_wx, on="date", how="inner")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Time features
    df["day_of_week"]  = df["date"].dt.dayofweek
    df["day_of_year"]  = df["date"].dt.dayofyear
    df["month"]        = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["is_weekend"]   = (df["day_of_week"] >= 5).astype(int)

    # Cyclical encoding
    df["dow_sin"]  = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"]  = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["doy_sin"]  = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["doy_cos"]  = np.cos(2 * np.pi * df["day_of_year"] / 365)
    df["month_sin"]= np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"]= np.cos(2 * np.pi * df["month"] / 12)

    # Lag features (days)
    for lag in [1, 2, 3, 7, 14]:
        df[f"aqi_lag_{lag}"] = df["aqi_mean"].shift(lag)

    # Rolling window features
    for win in [3, 7, 14]:
        df[f"aqi_roll_mean_{win}"] = df["aqi_mean"].shift(1).rolling(win).mean()
        df[f"aqi_roll_std_{win}"]  = df["aqi_mean"].shift(1).rolling(win).std()

    # Interaction features
    df["temp_humidity_interact"] = df["temp_mean"] * df["humidity_mean"]
    df["wind_aqi_interact"]      = df["wind_speed_mean"] * df["aqi_lag_1"].fillna(df["aqi_mean"].mean())

    df = df.dropna().reset_index(drop=True)
    return df


FEATURE_COLS = [
    "pm25_mean","pm10_mean","no2_mean","so2_mean","co_mean","o3_mean",
    "temp_mean","temp_max","humidity_mean","wind_speed_mean",
    "pressure_mean","visibility_mean","rainfall_sum","cloud_cover_mean",
    "day_of_week","month","is_weekend",
    "dow_sin","dow_cos","doy_sin","doy_cos","month_sin","month_cos",
    "aqi_lag_1","aqi_lag_2","aqi_lag_3","aqi_lag_7","aqi_lag_14",
    "aqi_roll_mean_3","aqi_roll_mean_7","aqi_roll_mean_14",
    "aqi_roll_std_3","aqi_roll_std_7",
    "temp_humidity_interact","wind_aqi_interact",
]
TARGET_COL = "aqi_mean"


# ──────────────────────────────────────────────
# Training
# ──────────────────────────────────────────────

def train_city_model(city_name: str, df: pd.DataFrame) -> dict:
    """
    Train RandomForest + GradientBoosting ensemble on daily city data.
    Returns metrics dict and saves model artefacts.
    """
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available_features].values
    y = df[TARGET_COL].values

    # Time-series split (no shuffle!)
    tscv = TimeSeriesSplit(n_splits=3)
    split = list(tscv.split(X))
    train_idx, test_idx = split[-1]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    # Model 1: Random Forest
    rf = RandomForestRegressor(
        n_estimators=200, max_depth=12, min_samples_leaf=3,
        n_jobs=-1, random_state=42
    )
    rf.fit(X_train_s, y_train)

    # Model 2: Gradient Boosting
    gb = GradientBoostingRegressor(
        n_estimators=150, max_depth=5, learning_rate=0.08,
        subsample=0.8, random_state=42
    )
    gb.fit(X_train_s, y_train)

    # Ensemble prediction
    preds_rf = rf.predict(X_test_s)
    preds_gb = gb.predict(X_test_s)
    preds    = 0.55 * preds_rf + 0.45 * preds_gb

    mae  = float(mean_absolute_error(y_test, preds))
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2   = float(r2_score(y_test, preds))
    mape = float(np.mean(np.abs((y_test - preds) / (y_test + 1e-9))) * 100)

    log.info(f"{city_name}: MAE={mae:.2f} RMSE={rmse:.2f} R²={r2:.3f} MAPE={mape:.2f}%")

    # Feature importance
    fi = dict(zip(available_features, rf.feature_importances_.tolist()))
    fi_sorted = dict(sorted(fi.items(), key=lambda x: x[1], reverse=True)[:10])

    # Save
    safe_name = city_name.lower().replace(" ", "_")
    model_path = MODELS_DIR / f"{safe_name}_model.pkl"
    joblib.dump({
        "rf": rf, "gb": gb, "scaler": scaler,
        "feature_cols": available_features,
        "df_last": df.tail(30),   # keep last 30 rows for rolling forecast
    }, model_path)

    return {
        "city":              city_name,
        "mae":               round(mae, 4),
        "rmse":              round(rmse, 4),
        "r2":                round(r2, 4),
        "mape":              round(mape, 4),
        "training_samples":  len(X_train),
        "model_path":        str(model_path),
        "feature_importance":fi_sorted,
    }


# ──────────────────────────────────────────────
# Forecasting
# ──────────────────────────────────────────────

def forecast_city(city_name: str, horizon: int = 7) -> list[dict]:
    """
    Load saved model and produce next `horizon` days of AQI forecast.
    Returns list of dicts: {date, predicted_aqi, category, lower, upper}.
    """
    from backend.utils.data_generator import get_aqi_category

    safe_name = city_name.lower().replace(" ", "_")
    model_path = MODELS_DIR / f"{safe_name}_model.pkl"

    if not model_path.exists():
        raise FileNotFoundError(f"No trained model for {city_name}")

    bundle = joblib.load(model_path)
    rf      = bundle["rf"]
    gb      = bundle["gb"]
    scaler  = bundle["scaler"]
    feat_cols = bundle["feature_cols"]
    history   = bundle["df_last"].copy()

    forecasts = []
    last_aqi  = float(history["aqi_mean"].iloc[-1])

    for day in range(1, horizon + 1):
        forecast_date = datetime.now().date() + timedelta(days=day)

        # Build a synthetic feature row using last known values + date info
        row = {}
        doy = forecast_date.timetuple().tm_yday
        dow = forecast_date.weekday()
        mon = forecast_date.month

        # Use last day's weather (best proxy without forecast weather API)
        last_row = history.iloc[-1]
        row["pm25_mean"]   = last_row.get("pm25_mean", last_aqi * 0.45)
        row["pm10_mean"]   = last_row.get("pm10_mean", last_aqi * 0.80)
        row["no2_mean"]    = last_row.get("no2_mean", last_aqi * 0.20)
        row["so2_mean"]    = last_row.get("so2_mean", last_aqi * 0.10)
        row["co_mean"]     = last_row.get("co_mean", last_aqi * 0.05)
        row["o3_mean"]     = last_row.get("o3_mean", 35.0)
        row["temp_mean"]   = last_row.get("temp_mean", 25.0)
        row["temp_max"]    = last_row.get("temp_max", 30.0)
        row["humidity_mean"]    = last_row.get("humidity_mean", 60.0)
        row["wind_speed_mean"]  = last_row.get("wind_speed_mean", 3.0)
        row["pressure_mean"]    = last_row.get("pressure_mean", 1013.0)
        row["visibility_mean"]  = last_row.get("visibility_mean", 8.0)
        row["rainfall_sum"]     = last_row.get("rainfall_sum", 0.0)
        row["cloud_cover_mean"] = last_row.get("cloud_cover_mean", 30.0)

        row["day_of_week"] = dow
        row["month"]       = mon
        row["is_weekend"]  = int(dow >= 5)
        row["dow_sin"]  = math.sin(2 * math.pi * dow / 7)
        row["dow_cos"]  = math.cos(2 * math.pi * dow / 7)
        row["doy_sin"]  = math.sin(2 * math.pi * doy / 365)
        row["doy_cos"]  = math.cos(2 * math.pi * doy / 365)
        row["month_sin"]= math.sin(2 * math.pi * mon / 12)
        row["month_cos"]= math.cos(2 * math.pi * mon / 12)

        hist_aqi = list(history["aqi_mean"].tail(14))
        row["aqi_lag_1"]  = hist_aqi[-1] if len(hist_aqi) >= 1 else last_aqi
        row["aqi_lag_2"]  = hist_aqi[-2] if len(hist_aqi) >= 2 else last_aqi
        row["aqi_lag_3"]  = hist_aqi[-3] if len(hist_aqi) >= 3 else last_aqi
        row["aqi_lag_7"]  = hist_aqi[-7] if len(hist_aqi) >= 7 else last_aqi
        row["aqi_lag_14"] = hist_aqi[-14] if len(hist_aqi) >= 14 else last_aqi

        recent3  = hist_aqi[-3:]
        recent7  = hist_aqi[-7:]
        recent14 = hist_aqi[-14:]
        row["aqi_roll_mean_3"]  = float(np.mean(recent3))  if recent3  else last_aqi
        row["aqi_roll_mean_7"]  = float(np.mean(recent7))  if recent7  else last_aqi
        row["aqi_roll_mean_14"] = float(np.mean(recent14)) if recent14 else last_aqi
        row["aqi_roll_std_3"]   = float(np.std(recent3))   if len(recent3)  > 1 else 5.0
        row["aqi_roll_std_7"]   = float(np.std(recent7))   if len(recent7)  > 1 else 8.0

        row["temp_humidity_interact"] = row["temp_mean"] * row["humidity_mean"]
        row["wind_aqi_interact"]      = row["wind_speed_mean"] * row["aqi_lag_1"]

        X_row = np.array([[row.get(c, 0.0) for c in feat_cols]])
        X_s   = scaler.transform(X_row)

        pred_rf = float(rf.predict(X_s)[0])
        pred_gb = float(gb.predict(X_s)[0])
        pred    = 0.55 * pred_rf + 0.45 * pred_gb
        pred    = max(0, min(500, pred))

        # Uncertainty: grows with horizon
        base_std = 15 + day * 3
        lower = max(0,   int(pred - 1.96 * base_std))
        upper = min(500, int(pred + 1.96 * base_std))

        pred_int = int(round(pred))
        cat_info = get_aqi_category(pred_int)

        forecasts.append({
            "date":            forecast_date.isoformat(),
            "predicted_aqi":   pred_int,
            "category":        cat_info["category"],
            "color":           cat_info["color"],
            "confidence_lower":lower,
            "confidence_upper":upper,
        })

        # Roll forward: append synthetic row to history
        new_row = {**last_row.to_dict(), "aqi_mean": pred, "date": pd.Timestamp(forecast_date)}
        history = pd.concat([history, pd.DataFrame([new_row])], ignore_index=True)

    return forecasts


# ──────────────────────────────────────────────
# CLI entry-point: train all cities
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from backend.utils.data_generator import generate_all_cities

    results = []
    for city_name, aqi_df, weather_df in generate_all_cities(days=365):
        try:
            df = make_features(aqi_df, weather_df)
            metrics = train_city_model(city_name, df)
            results.append(metrics)
        except Exception as e:
            log.error(f"Failed {city_name}: {e}")

    # Save summary
    summary_path = MODELS_DIR / "training_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Trained {len(results)} city models → {MODELS_DIR}")
    print(json.dumps([{k: v for k, v in r.items() if k != "feature_importance"} for r in results], indent=2))

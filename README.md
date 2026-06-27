# 🌍 AQI Forecaster – Air Quality Intelligence & Forecasting System

A full-stack data science application that monitors, analyzes, and forecasts the **Air Quality Index (AQI)** for major Indian cities using machine learning and interactive data visualization.

The system combines **time-series feature engineering**, **ensemble machine learning models**, **Flask REST APIs**, **MySQL**, and an interactive dashboard built with **Leaflet.js** and **Chart.js** to provide real-time AQI monitoring, historical trend analysis, and multi-day air quality forecasting.

---
## 🚀 Features

### 🌫 Air Quality Forecasting

- AQI prediction using ensemble machine learning models
- Random Forest + Gradient Boosting
- Multi-day AQI forecasting
- Confidence Interval estimation

### 📊 Data Science

- Feature Engineering
- Lag Features
- Rolling Statistics
- Cyclical Time Encoding
- Time-Series Modeling

### 🌐 Interactive Dashboard

- Live AQI Map
- Historical Trend Charts
- City-wise Analytics
- Interactive Dashboard

### ⚙ Backend

- Flask REST APIs
- SQLAlchemy ORM
- Background Model Training
- MySQL Database

### 📈 Visualization

- Leaflet.js Interactive Maps
- Chart.js Graphs
- AQI Trend Visualization
- Forecast Charts
---

## 📁 Project Structure

```
aqi_forecaster/
├── backend/
│   ├── app.py                      ← Flask application entry point
│   ├── models/
│   │   └── db_models.py            ← SQLAlchemy ORM models
│   ├── routes/
│   │   └── api.py                  ← REST API endpoints
│   ├── ml/
│   │   └── forecaster.py           ← ML training & inference engine
│   └── utils/
│       ├── data_generator.py       ← AQI + weather data simulator
│       └── seed_db.py              ← Database seeder script
├── frontend/
│   ├── templates/
│   │   └── index.html              ← Main dashboard template
│   └── static/
│       ├── css/style.css           ← Dark atmospheric theme
│       └── js/main.js              ← Map, charts, API calls
├── database/
│   └── schema.sql                  ← MySQL schema + seed cities
├── notebooks/
│   └── AQI_EDA_and_Forecasting.ipynb  ← Full DS notebook
├── models/                         ← Saved .pkl model files
├── data/                           ← EDA plot outputs
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- MySQL 8.0+

### 2. Clone & Install
```bash
git clone https://github.com/yourusername/aqi-forecaster.git
cd aqi_forecaster
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your MySQL credentials
```

### 4. Setup MySQL Database
```sql
-- In MySQL shell:
mysql -u root -p
CREATE DATABASE aqi_forecaster;
EXIT;

-- Or run the schema directly:
mysql -u root -p aqi_forecaster < database/schema.sql
```

### 5. Seed Database (30 days of historical data)
```bash
python backend/utils/seed_db.py --days 30
# For more history (slower but better models):
python backend/utils/seed_db.py --days 365
```

### 6. Train ML Models
```bash
# Train all 20 city models (takes ~2-3 minutes)
python backend/ml/forecaster.py
# OR use the API endpoint after starting the server
```

### 7. Start the Server
```bash
python backend/app.py
# Server runs at http://localhost:5005
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cities` | All cities with current AQI + coordinates |
| GET | `/api/city/<name>/current` | Current AQI + weather for a city |
| GET | `/api/city/<name>/history?days=30` | Daily AQI history |
| GET | `/api/city/<name>/forecast?days=7` | 7-day ML forecast |
| GET | `/api/city/<name>/pollutants` | Pollutant breakdown |
| GET | `/api/compare?cities=Delhi,Mumbai` | Multi-city comparison |
| GET | `/api/stats/summary` | National AQI statistics |
| POST | `/api/train` | Trigger background model training |
| GET | `/api/models` | Model training status & metrics |

### Example API Call
```bash
curl http://localhost:5005/api/city/Delhi/forecast?days=7
```

---

## 🧠 Data Science Deep Dive

### Model Architecture
```
Hourly AQI + Weather Data (365 days)
        ↓
Daily Aggregation (mean, max, min, std)
        ↓
Feature Engineering (35+ features):
  • Lag features:    aqi_lag_1, _2, _3, _7, _14
  • Rolling:         roll_mean_3, _7, _14 | roll_std_3, _7
  • Cyclical:        sin/cos encoding for DOW, DOY, month
  • Weather:         temp, humidity, wind, pressure, visibility
  • Interactions:    temp×humidity, wind×aqi_lag
        ↓
Time-Series Split (3-fold, no shuffle)
        ↓
  Model A: RandomForestRegressor (200 trees, depth=12)
  Model B: GradientBoostingRegressor (150 trees, lr=0.08)
        ↓
  Ensemble: 0.55 × RF + 0.45 × GB
        ↓
7-Day Rolling Forecast + 95% Confidence Interval
```

### Feature Importance (Top features for Delhi)
1. `aqi_lag_1` — Yesterday's AQI (~35% importance)
2. `aqi_roll_mean_7` — 7-day rolling mean
3. `aqi_lag_7` — Same day last week
4. `pm25_mean` — PM2.5 concentration
5. `humidity_mean` — Relative humidity
6. `wind_speed_mean` — Dispersion factor
7. `doy_sin/cos` — Seasonal cyclical encoding
8. `temp_humidity_interact` — Interaction term

### Typical Model Performance (Delhi)
| Metric | Value |
|--------|-------|
| MAE | ~18–25 AQI units |
| RMSE | ~28–38 AQI units |
| R² | 0.85–0.92 |
| MAPE | 12–18% |

---

## 🗄️ Database Schema

```
cities            ← 20 Indian cities with lat/lon
aqi_readings      ← Hourly AQI + pollutants (PM2.5, PM10, NO2, SO2, CO, O3)
weather_readings  ← Hourly weather (temp, humidity, wind, pressure, visibility)
aqi_forecasts     ← Stored ML predictions per city per day
model_registry    ← Model versions, training metrics, paths
```

---

## 🎨 Dashboard Features

- **Interactive Map** — Leaflet.js with CartoDB dark tiles; AQI bubble markers sized + colored by severity
- **Live Rankings** — Cities sorted by current AQI in sidebar
- **City Detail Panel** — Click any city for full breakdown
  - Big AQI display with health advice
  - Pollutant grid (PM2.5, PM10, NO2, SO2, CO, O3)
  - Weather strip (temp, humidity, wind, visibility)
  - 30-day history chart
  - 7-day forecast chart + confidence band
  - Forecast table with predicted category
- **Auto-refresh** — Data refreshes every 60 seconds
- **Category Distribution** — Doughnut chart of AQI categories

---

## 📊 Notebooks

Open `notebooks/AQI_EDA_and_Forecasting.ipynb` in Jupyter:
```bash
pip install jupyter
jupyter notebook
```

The notebook covers:
1. Data generation & loading
2. EDA (time series, distributions, seasonal patterns)
3. Correlation analysis (AQI vs weather)
4. Feature engineering walkthrough
5. Model training & evaluation
6. 7-day forecast visualization
7. Feature importance analysis
8. Multi-city comparison

---

## 🔌 Real Data Integration (Production)

Replace simulated data with real APIs:

| Data Source | API | What it provides |
|------------|-----|-----------------|
| CPCB (India) | `https://api.data.gov.in/` | Official Indian AQI readings |
| OpenWeatherMap | `api.openweathermap.org` | Weather + air pollution |
| IQAir | `api.airvisual.com` | Global AQI data |

Replace calls in `data_generator.py` → `generate_historical_aqi()` and `generate_historical_weather()` with real API requests, then store results in MySQL via the ORM models.

---

## 🛠️ Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.10+ |
| Web Framework | Flask 3.0 |
| Database | MySQL 8.0 + SQLAlchemy ORM |
| ML Models | Scikit-learn (RandomForest, GradientBoosting) |
| Data Processing | Pandas, NumPy |
| Visualization | Chart.js, Matplotlib, Seaborn |
| Maps | Leaflet.js |
| Frontend | Vanilla HTML/CSS/JS |
| Model Storage | Joblib (.pkl files) |

---

## 👩‍💻 Author

**Mehak Khan** — BCA (Data Science), Jagannath University  
GitHub: [github.com/khan2234mehak](https://github.com/khan2234mehak)

---

## 📝 License
MIT License — feel free to use, modify, and distribute.

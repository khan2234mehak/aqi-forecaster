-- =====================================================
-- AQI Forecaster Database Schema
-- =====================================================

CREATE DATABASE IF NOT EXISTS aqi_forecaster;
USE aqi_forecaster;

-- Cities table
CREATE TABLE IF NOT EXISTS cities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 6) NOT NULL,
    longitude DECIMAL(10, 6) NOT NULL,
    population BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AQI Historical Data
CREATE TABLE IF NOT EXISTS aqi_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_id INT NOT NULL,
    recorded_at DATETIME NOT NULL,
    aqi INT NOT NULL,
    category VARCHAR(50),         -- Good, Satisfactory, Moderate, Poor, Very Poor, Severe
    pm25 DECIMAL(8, 2),
    pm10 DECIMAL(8, 2),
    no2 DECIMAL(8, 2),
    so2 DECIMAL(8, 2),
    co DECIMAL(8, 2),
    o3 DECIMAL(8, 2),
    nh3 DECIMAL(8, 2),
    FOREIGN KEY (city_id) REFERENCES cities(id),
    INDEX idx_city_date (city_id, recorded_at)
);

-- Weather Data
CREATE TABLE IF NOT EXISTS weather_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_id INT NOT NULL,
    recorded_at DATETIME NOT NULL,
    temperature DECIMAL(6, 2),      -- Celsius
    humidity DECIMAL(5, 2),         -- %
    wind_speed DECIMAL(6, 2),       -- m/s
    wind_direction INT,             -- degrees
    pressure DECIMAL(8, 2),         -- hPa
    visibility DECIMAL(6, 2),       -- km
    dew_point DECIMAL(6, 2),
    cloud_cover INT,                -- %
    rainfall DECIMAL(6, 2),         -- mm
    FOREIGN KEY (city_id) REFERENCES cities(id),
    INDEX idx_city_date (city_id, recorded_at)
);

-- AQI Forecasts (model predictions)
CREATE TABLE IF NOT EXISTS aqi_forecasts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_id INT NOT NULL,
    forecast_date DATE NOT NULL,
    forecast_for DATE NOT NULL,      -- target prediction date
    predicted_aqi INT NOT NULL,
    predicted_category VARCHAR(50),
    confidence_lower INT,
    confidence_upper INT,
    model_used VARCHAR(100),
    FOREIGN KEY (city_id) REFERENCES cities(id),
    INDEX idx_city_forecast (city_id, forecast_for)
);

-- Model metadata
CREATE TABLE IF NOT EXISTS model_registry (
    id INT AUTO_INCREMENT PRIMARY KEY,
    city_id INT NOT NULL,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    trained_at DATETIME,
    mae DECIMAL(8, 4),
    rmse DECIMAL(8, 4),
    mape DECIMAL(8, 4),
    r2_score DECIMAL(8, 4),
    training_samples INT,
    model_path VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (city_id) REFERENCES cities(id)
);

-- Seed Indian cities
INSERT INTO cities (name, state, latitude, longitude, population) VALUES
('Delhi', 'Delhi', 28.6139, 77.2090, 32941000),
('Mumbai', 'Maharashtra', 19.0760, 72.8777, 20667656),
('Kolkata', 'West Bengal', 22.5726, 88.3639, 14850000),
('Chennai', 'Tamil Nadu', 13.0827, 80.2707, 10971108),
('Bangalore', 'Karnataka', 12.9716, 77.5946, 12765000),
('Hyderabad', 'Telangana', 17.3850, 78.4867, 10534418),
('Ahmedabad', 'Gujarat', 23.0225, 72.5714, 8059441),
('Pune', 'Maharashtra', 18.5204, 73.8567, 7276000),
('Jaipur', 'Rajasthan', 26.9124, 75.7873, 3073350),
('Lucknow', 'Uttar Pradesh', 26.8467, 80.9462, 3382900),
('Kanpur', 'Uttar Pradesh', 26.4499, 80.3319, 3020243),
('Nagpur', 'Maharashtra', 21.1458, 79.0882, 2742000),
('Indore', 'Madhya Pradesh', 22.7196, 75.8577, 3239000),
('Bhopal', 'Madhya Pradesh', 23.2599, 77.4126, 2368145),
('Patna', 'Bihar', 25.5941, 85.1376, 2290419),
('Varanasi', 'Uttar Pradesh', 25.3176, 82.9739, 1432280),
('Agra', 'Uttar Pradesh', 27.1767, 78.0081, 1760285),
('Surat', 'Gujarat', 21.1702, 72.8311, 6584890),
('Coimbatore', 'Tamil Nadu', 11.0168, 76.9558, 2136916),
('Visakhapatnam', 'Andhra Pradesh', 17.6868, 83.2185, 2035922);

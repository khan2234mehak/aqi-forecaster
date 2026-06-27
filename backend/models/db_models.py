"""
SQLAlchemy ORM models for AQI Forecaster
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Date, Boolean, BigInteger, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()


class City(Base):
    __tablename__ = "cities"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(100), nullable=False)
    state      = Column(String(100), nullable=False)
    latitude   = Column(Float, nullable=False)
    longitude  = Column(Float, nullable=False)
    population = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)

    aqi_readings     = relationship("AQIReading",     back_populates="city", lazy="dynamic")
    weather_readings = relationship("WeatherReading", back_populates="city", lazy="dynamic")
    forecasts        = relationship("AQIForecast",    back_populates="city", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "state": self.state,
            "latitude": self.latitude, "longitude": self.longitude,
            "population": self.population,
        }


class AQIReading(Base):
    __tablename__ = "aqi_readings"
    __table_args__ = (Index("idx_city_date", "city_id", "recorded_at"),)

    id          = Column(Integer, primary_key=True, autoincrement=True)
    city_id     = Column(Integer, ForeignKey("cities.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    aqi         = Column(Integer, nullable=False)
    category    = Column(String(50))
    pm25        = Column(Float)
    pm10        = Column(Float)
    no2         = Column(Float)
    so2         = Column(Float)
    co          = Column(Float)
    o3          = Column(Float)
    nh3         = Column(Float)

    city = relationship("City", back_populates="aqi_readings")

    def to_dict(self):
        return {
            "recorded_at": self.recorded_at.isoformat(),
            "aqi": self.aqi, "category": self.category,
            "pm25": self.pm25, "pm10": self.pm10,
            "no2": self.no2, "so2": self.so2,
            "co": self.co, "o3": self.o3, "nh3": self.nh3,
        }


class WeatherReading(Base):
    __tablename__ = "weather_readings"
    __table_args__ = (Index("idx_weather_city_date", "city_id", "recorded_at"),)

    id             = Column(Integer, primary_key=True, autoincrement=True)
    city_id        = Column(Integer, ForeignKey("cities.id"), nullable=False)
    recorded_at    = Column(DateTime, nullable=False)
    temperature    = Column(Float)
    humidity       = Column(Float)
    wind_speed     = Column(Float)
    wind_direction = Column(Integer)
    pressure       = Column(Float)
    visibility     = Column(Float)
    dew_point      = Column(Float)
    cloud_cover    = Column(Integer)
    rainfall       = Column(Float)

    city = relationship("City", back_populates="weather_readings")

    def to_dict(self):
        return {
            "recorded_at": self.recorded_at.isoformat(),
            "temperature": self.temperature, "humidity": self.humidity,
            "wind_speed": self.wind_speed, "pressure": self.pressure,
            "visibility": self.visibility, "rainfall": self.rainfall,
        }


class AQIForecast(Base):
    __tablename__ = "aqi_forecasts"
    __table_args__ = (Index("idx_forecast_city", "city_id", "forecast_for"),)

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    city_id            = Column(Integer, ForeignKey("cities.id"), nullable=False)
    forecast_date      = Column(Date, nullable=False)
    forecast_for       = Column(Date, nullable=False)
    predicted_aqi      = Column(Integer, nullable=False)
    predicted_category = Column(String(50))
    confidence_lower   = Column(Integer)
    confidence_upper   = Column(Integer)
    model_used         = Column(String(100))

    city = relationship("City", back_populates="forecasts")

    def to_dict(self):
        return {
            "forecast_for": self.forecast_for.isoformat(),
            "predicted_aqi": self.predicted_aqi,
            "predicted_category": self.predicted_category,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
        }


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    city_id          = Column(Integer, ForeignKey("cities.id"))
    model_name       = Column(String(100))
    model_version    = Column(String(50))
    trained_at       = Column(DateTime)
    mae              = Column(Float)
    rmse             = Column(Float)
    mape             = Column(Float)
    r2_score         = Column(Float)
    training_samples = Column(Integer)
    model_path       = Column(String(255))
    is_active        = Column(Boolean, default=True)


def get_engine(db_url: str):
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)


def init_db(engine):
    Base.metadata.create_all(engine)

# app/models/forecast_reliability.py
from sqlalchemy import Column, Integer, Float, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class ForecastReliability(Base):
    __tablename__ = "forecast_reliability"
    id = Column(Integer, primary_key=True)
    source_name = Column(String, index=True, nullable=False)
    metric = Column(String, index=True, nullable=False)
    as_of_date = Column(Date, index=True, nullable=False)
    score = Column(Integer, nullable=False)        # 0–100
    mape = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    smape = Column(Float, nullable=False)
    folds = relationship("ForecastReliabilityFold", cascade="all,delete-orphan")

class ForecastReliabilityFold(Base):
    __tablename__ = "forecast_reliability_fold"
    id = Column(Integer, primary_key=True)
    reliability_id = Column(Integer, ForeignKey("forecast_reliability.id", ondelete="CASCADE"))
    fold_index = Column(Integer, nullable=False)
    mae = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    mape = Column(Float, nullable=False)
    bias = Column(Float, nullable=False) # calibration proxy
from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class ForecastModel(Base):
    __tablename__ = "forecast_models"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    metric = Column(String(128), nullable=False, index=True)
    model_name = Column(String(64), nullable=False, default="SARIMAX")
    model_params = Column(JSONB, nullable=False, default=dict)
    window_n = Column(Integer, nullable=False)
    horizon_n = Column(Integer, nullable=False, default=7)
    trained_at = Column(DateTime(timezone=True), nullable=False)
    train_start = Column(Date, nullable=True)
    train_end = Column(Date, nullable=True)
    mape = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    source = relationship("Source", backref="forecast_models")

from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, UniqueConstraint
from app.db.base import Base

class ForecastResults(Base):
    __tablename__ = "forecast_results"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    metric = Column(String(64), nullable=False)
    target_date = Column(Date, nullable=False)
    yhat = Column(Float, nullable=False)
    yhat_lower = Column(Float, nullable=True)
    yhat_upper = Column(Float, nullable=True)
    model_version = Column(String(32), nullable=True)
    __table_args__ = (UniqueConstraint("source_id","metric","target_date", name="uq_forecast_day"),)

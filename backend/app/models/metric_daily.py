from sqlalchemy import Column, Date, String, Integer, Numeric, PrimaryKeyConstraint, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class MetricDaily(Base):
    __tablename__ = "metric_daily"

    metric_date = Column(Date, nullable=False)          # yyyy-mm-dd
    source_id   = Column(Integer, ForeignKey("sources.id"), nullable=False)
    metric      = Column(String(64), nullable=False)

    # aggregations
    value_sum   = Column(Numeric(18, 4), nullable=False, default=0)
    value_avg   = Column(Numeric(18, 4), nullable=False, default=0)
    value_count = Column(Integer,          nullable=False, default=0)

    __table_args__ = (
        PrimaryKeyConstraint("metric_date", "source_id", "metric", name="pk_metric_daily"),
    )

    # FK convenience
    source = relationship("Source", backref="metric_daily")

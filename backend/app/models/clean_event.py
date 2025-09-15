from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class CleanEvent(Base):
    __tablename__ = "clean_events"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    metric = Column(String(255), nullable=False)
    value = Column(Float, nullable=False)

    source = relationship("Source")

    __table_args__ = (
        UniqueConstraint("source_id", "ts", "metric", name="uq_clean_events_src_ts_metric"),
        Index("ix_clean_events_ts", "ts"),
        Index("ix_clean_events_source_id", "source_id"),
    )

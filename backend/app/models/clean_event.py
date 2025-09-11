from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

class CleanEvent(Base):
    __tablename__= "clean_events"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), index=True)
    ts = Column(DateTime, index=True)
    metric = Column(String, index=True)
    value = Column(Float)
    sources = relationship("Source")
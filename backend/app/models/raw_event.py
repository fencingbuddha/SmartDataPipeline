from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from app.db.types import EncryptedJSON


class RawEvent(Base):
    """
    RawEvent = immutable staging record from uploaded files.
    Stores one row/object exactly as received before normalization.
    """

    __tablename__ = "raw_events"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer,
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    received_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    payload = Column(EncryptedJSON, nullable=False)  # raw row/object contents

    # Relationships
    source = relationship("Source", back_populates="raw_events")

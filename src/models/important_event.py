from database import Base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class ImportantEvent(Base):
    __tablename__ = "important_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    event_date = Column(DateTime, nullable=False)
    recurring = Column(Boolean, default=False)
    created_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", backref="important_events")

    __table_args__ = (
        Index("idx_important_event_user", "user_id", "event_date"),
        Index("idx_important_event_date", "event_date"),
    )

from utils.database.database import Base
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship


class PromocodeUsage(Base):
    """Tracks which user has used which promocode — enforces one-use-per-user limit."""

    __tablename__ = "promocode_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=False)
    used_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User")
    promocode = relationship("Promocode")

    __table_args__ = (
        UniqueConstraint("user_id", "promocode_id", name="uq_user_promocode"),
        Index("idx_promocode_usage_user", "user_id"),
        Index("idx_promocode_usage_code", "promocode_id"),
    )

from utils.database.database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import relationship


class CourierReview(Base):
    __tablename__ = "courier_reviews"

    id = Column(Integer, primary_key=True, index=True)
    reviewed_by = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # Customer who left the review
    reviewed = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # Courier being reviewed
    rate = Column(Integer, nullable=False)  # Rating from 0 to 5
    comment = Column(Text, nullable=True)  # Optional comment
    created_at = Column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    reviewer = relationship(
        "User", foreign_keys=[reviewed_by], backref="courier_reviews_given"
    )
    reviewed_user = relationship(
        "User", foreign_keys=[reviewed], backref="courier_reviews_received"
    )

    __table_args__ = (
        Index("idx_courier_review_reviewer", "reviewed_by", "created_at"),
        Index("idx_courier_review_reviewed", "reviewed", "created_at"),
        Index("idx_courier_review_rate", "rate"),
    )

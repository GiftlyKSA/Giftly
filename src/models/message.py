from database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True
    )
    sender_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )  # Nullable for system messages
    content = Column(Text, nullable=False)
    sent_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    message_type = Column(
        String(20), nullable=False, default="text"
    )  # 'text', 'invoice', 'image', 'video', 'system'
    media_type = Column(
        String(20), nullable=True
    )  # 'image' or 'video' when message_type is 'image' or 'video'
    # Invoice specific fields
    invoice_description = Column(Text, nullable=True)
    invoice_gift_price = Column(Integer, nullable=True)  # in cents/halaym
    invoice_service_fee = Column(Integer, nullable=True)
    invoice_delivery_fee = Column(Integer, nullable=True)
    invoice_total = Column(Integer, nullable=True)
    # Media specific fields
    media_url = Column(String, nullable=True)  # URL to uploaded media file
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")

    __table_args__ = (
        Index("idx_message_conversation", "conversation_id", "sent_at"),
        Index("idx_message_sender", "sender_id", "sent_at"),
        Index("idx_message_type", "message_type", "sent_at"),
        Index("idx_message_media_type", "media_type"),
    )

from utils.database.database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(100), nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_audit_log_admin", "admin_id", "created_at"),
        Index("idx_audit_log_target", "target_type", "target_id"),
        Index("idx_audit_log_action", "action"),
    )

    def __str__(self):
        return f"[{self.action}] admin={self.admin_id} target={self.target_type}:{self.target_id}"

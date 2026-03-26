from enum import Enum

class OrderStatus(Enum):
    NEW = "new"
    RECEIVED_BY_COURIER = "received by courier"
    PAID = "paid"
    IN_PROGRESS_TO_DO = "in progress to do"
    CANCELLED = "cancelled"
    DONE = "done"
    IN_PROGRESS_TO_DELIVER = "in progress to deliver"

class InvoiceStatus(Enum):
    NEW = "new"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    OTHER = "other"

class PaymentMethod(Enum):
    WALLET = "wallet"
    CREDIT_CARD = "credit_card"
    APPLE_PAY = "apple_pay"
    MADA = "mada"

class PaymentStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class DepositRequestStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class UserRole(Enum):
    CUSTOMER = "Customer"
    COURIER = "Courier"

class ImageType(Enum):
    CHAT = "chat"
    ORDER = "order"
    GALLERY = "gallery"

class ConversationStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"

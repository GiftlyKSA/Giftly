# Giftly Marketplace App - Code Review and Recommendations

## Overview
This document reviews the Giftly marketplace app codebase and provides recommendations for improvements based on the described workflow where customers place gift orders, couriers in the same city receive notifications, accept orders, coordinate via chat, create invoices, process payments, and complete deliveries.

## Current Implementation Analysis

### Strengths
1. **Modular Structure**: Clean separation of concerns with models, routers, schemas, and utils
2. **Proper Validation**: Input validation for file uploads, city IDs, and user roles
3. **WebSocket Integration**: Real-time communication for order notifications and chat
4. **Soft Delete Pattern**: Models include `deleted_at` fields for soft deletion
5. **Database Indexing**: Proper indexing on frequently queried fields
6. **Security Headers**: Implementation of security middleware (HTTPS forcing, security headers)
7. **Admin Dashboard**: SQLAdmin integration for easy data management
8. **File Upload Handling**: Proper image validation and upload processing
9. **Background Tasks**: Used for temporary file cleanup (invoice PDFs)
10. **Event Emitters**: WebSocket events for order status changes and chat messages

### Areas for Improvement

## 1. Order Status Flow Enhancements
**Issue**: The current order status flow doesn't fully match the described workflow where payment is reserved until order completion.

**Current Flow**:
- Order created → Status: NEW
- Courier accepts → Status: RECEIVED_BY_COURIER
- Courier can manually update status (in_progress, ready_for_delivery, etc.)
- Customer confirms delivery → `customer_confirmed = True`
- Courier completes order → Status: DONE (only after invoice paid)

**Missing Elements**:
- Payment reservation/authorization step
- Clear distinction between "payment authorized" and "payment captured"
- Invoice creation typically happens BEFORE courier starts work (not after agreement)
- No explicit "payment pending" or "payment authorized" states

**Recommendation**:
Add explicit payment-related order statuses:
```python
# In enums.py OrderStatus
PAYMENT_PENDING = "payment pending"
PAYMENT_AUTHORIZED = "payment authorized"
AWAITING_PICKUP = "awaiting pickup"
```

Update workflow:
1. Order created → Status: NEW
2. Courier accepts → Status: RECEIVED_BY_COURIER
3. Courier creates invoice → Status: INVOICE_CREATED
4. Customer pays invoice → Status: PAYMENT_PENDING → PAYMENT_AUTHORIZED
5. Courier starts work → Status: AWAITING_PICKUP → IN_PROGRESS_TO_DO
6. Courier has item → Status: IN_PROGRESS_TO_DELIVER
7. Out for delivery → Status: OUT_FOR_DELIVERY
8. Customer confirms delivery → Status: AWAITING_CONFIRMATION
9. Order complete → Status: DONE

## 2. Invoice Creation Flow
**Issue**: Currently, couriers can create invoices immediately after accepting an order, but there's no mechanism to ensure the customer agrees to the price before work begins.

**Current Implementation**:
- Courier can create invoice via `/invoices/courier/create` endpoint
- Customer pays invoice via payment endpoints (not fully visible in provided code)
- Order completion requires paid invoice

**Recommendation**:
1. Add invoice approval workflow:
   - Courier creates invoice as DRAFT
   - Customer reviews and approves invoice
   - Only approved invoices can be paid
   - Changes to invoice require re-approval

2. Add invoice statuses:
```python
# In enums.py InvoiceStatus
DRAFT = "draft"
PENDING_APPROVAL = "pending approval"
APPROVED = "approved"
```

3. Modify order status to reflect invoice state:
   - Order status should not progress to IN_PROGRESS until invoice is APPROVED

## 3. Payment Flow Clarification
**Issue**: The payment flow is not clearly visible in the provided code snippets. Need to ensure:
- Payment authorization (not capture) happens when invoice is approved
- Payment capture happens when order is marked complete
- Proper handling of failed payments
- Refund workflow

**Recommendation**:
1. Add explicit payment authorization/capture separation:
   - When invoice is APPROVED: Authorize payment (reserve funds)
   - When order is COMPLETE: Capture payment (transfer funds)
   - If order cancelled after authorization: Release authorization

2. Add payment intent tracking:
   - Store payment processor transaction IDs
   - Track authorization vs capture amounts
   - Handle partial captures if needed

## 4. Notification System Improvements
**Issue**: While WebSocket notifications exist for new orders, there's no systematic notification for:
- Invoice creation/approval requests
- Payment status changes
- Order status updates beyond basic emit_order_status_change
- Chat message notifications when offline

**Recommendation**:
1. Enhance websocket_events.py with more specific events:
   - `emit_invoice_requires_approval`
   - `emit_payment_status_change`
   - `emit_order_timeline_update` (for detailed progress)

2. Consider implementing:
   - Push notifications for mobile apps (if applicable)
   - Email/SMS fallback for critical notifications
   - Notification preferences per user

## 5. Chat System Enhancements
**Issue**: Current chat implementation is functional but lacks features important for coordination:
- No file sharing beyond initial order images
- No location sharing (important for gift pickup/delivery coordination)
- No message read receipts
- No message reactions or quick responses

**Recommendation**:
1. Extend Message model:
   ```python
   # Add to models/message.py
   read_by = Column(JSON, nullable=True)  # List of user IDs who read the message
   reply_to_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
   ```

2. Add support for:
   - Location sharing (latitude/longitude)
   - File sharing (documents, screenshots of purchased items)
   - Quick response buttons ("Running late", "At location", "Need help")

## 6. Courier Availability and Matching
**Issue**: Current system shows all NEW orders to couriers in the same city, but lacks:
- Courier specialization/tags (gift types they handle)
- Distance-based ordering (show nearest orders first)
- Courier workload limits
- Schedule-based availability

**Recommendation**:
1. Enhance CourierProfile model:
   ```python
   # Add to models/courier/courier_profile.py
   specialties = Column(JSON)  # ["birthday", "anniversary", "flowers", etc]
   max_concurrent_orders = Column(Integer, default=3)
   preferred_radius_km = Column(Integer, default=10)
   ```

2. Modify available orders query:
   - Filter by courier specialties matching order description keywords
   - Sort by distance from courier's last known location
   - Respect max_concurrent_orders limit

## 7. Error Handling and Logging
**Issue**: While basic error handling exists, there are opportunities for improvement:
- Some exceptions are caught and logged generically
- Missing validation in edge cases
- Limited audit trail for critical operations

**Recommendation**:
1. Create custom exception handlers:
   ```python
   # In utils/exceptions.py
   class GiftlyException(Exception):
       def __init__(self, message, error_code=None, status_code=400):
           self.message = message
           self.error_code = error_code
           self.status_code = status_code
           super().__init__(self.message)
   ```

2. Add audit logging for:
   - Invoice creation/modification
   - Payment authorization/capture
   - Order status changes
   - Courier earnings updates

## 8. Database Performance Optimizations
**Issue**: Current indexing is good but could be enhanced for specific query patterns:
- Frequent queries by city_id + status
- Courier profile lookups by user_id + city_id
- Conversation lookups by participant IDs

**Recommendation**:
1. Add composite indexes:
   ```python
   # In order.py
   Index('idx_order_city_status_city', 'city_id', 'status', 'created_by_user_id')
   
   # In conversation.py
   Index('idx_conversation_participants', 'customer_id', 'courier_id')
   
   # In coupon_profile.py
   Index('idx_courier_profile_available', 'is_approved', 'is_available', 'city_id')
   ```

2. Consider read replicas for:
 

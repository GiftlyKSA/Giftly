from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Order
from websocket_manager import manager
from database import AsyncSessionLocal


async def emit_order_status_change(order_id: int, new_status: str, db: AsyncSession = None):
    """Emit order status change event to relevant users"""
    # Create a new session for this background operation to avoid conflicts
    async with AsyncSessionLocal() as session:
        # Get order details with courier information if assigned
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Order).options(selectinload(Order.assigned_to_user)).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            return

        event_data = {
            "event": "order_status_change",
            "data": {
                "order_id": order.order_id,
                "id": order.id,
                "status": new_status,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                "assigned_to_user_id": order.assigned_to_user_id,
                "created_by_user_id": order.created_by_user_id
            }
        }

        # Include courier information if order is assigned to a courier
        if order.assigned_to_user and new_status == "received by courier":
            event_data["data"]["courier_info"] = {
                "id": order.assigned_to_user.id,
                "name": order.assigned_to_user.name
            }

        # Send to customer
        await manager.send_to_user(order.created_by_user_id, event_data)

        # Send to assigned courier if exists
        if order.assigned_to_user_id:
            await manager.send_to_user(order.assigned_to_user_id, event_data)

        # If order is newly created (NEW status), also broadcast to couriers in the city
        if new_status == "new":
            await manager.broadcast_to_room({
                "event": "new_order",
                "data": {
                    "order_id": order.order_id,
                    "id": order.id,
                    "description": order.description,
                    "city_id": order.city_id,
                    "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                    "created_by_user_id": order.created_by_user_id
                }
            }, f"couriers_city_{order.city_id}")


async def emit_chat_message(conversation_id: int, message_data: dict, db: AsyncSession):
    """Emit chat message event"""
    event_data = {
        "event": "chat_message",
        "room": f"chat_{conversation_id}",
        "data": message_data
    }

    await manager.broadcast_to_room(event_data, f"chat_{conversation_id}")


async def emit_invoice_created(invoice_id: int, order_id: int):
    """Emit invoice creation event to relevant users"""
    async with AsyncSessionLocal() as session:
        # Get order details with invoice information
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Order).options(selectinload(Order.invoice)).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order or not order.invoice:
            return

        event_data = {
            "event": "invoice_created",
            "data": {
                "order_id": order.order_id,
                "id": order.id,
                "invoice_id": order.invoice.invoice_id,
                "invoice": {
                    "id": order.invoice.id,
                    "invoice_id": order.invoice.invoice_id,
                    "full_amount": order.invoice.full_amount,
                    "description": order.invoice.description,
                    "created_at": order.invoice.created_at.isoformat() if order.invoice.created_at else None
                },
                "status": order.status,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None
            }
        }

        # Send to customer
        await manager.send_to_user(order.created_by_user_id, event_data)

        # Send to assigned courier if exists
        if order.assigned_to_user_id:
            await manager.send_to_user(order.assigned_to_user_id, event_data)

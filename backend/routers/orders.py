from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select, desc
from database import get_db
from models import Order, City, User, OrderStatus, Conversation, CourierBalanceAddition, Invoice, Wallet, Payment, PaymentMethod, InvoiceStatus
from datetime import datetime
from schemas import CreateOrder, OrderResponse, CancelOrderRequest, AssignOrderRequest
from auth import get_current_user

router = APIRouter()

@router.post("/", response_model=OrderResponse)
async def create_order(order_data: CreateOrder, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Create a new order. Only authenticated users can create orders.
    City and delivery_date are mandatory, description is optional.
    """
    # Validate that city exists
    result = await db.execute(select(City).where(City.id == order_data.city_id))
    city = result.scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=400, detail="Invalid city ID")

    # Generate order_id
    result = await db.execute(select(func.max(Order.id)))
    max_id = result.scalar()
    if max_id is None:
        max_id = 0
    order_id = f"ORDR-{100000 + max_id + 1}"

    # Create the order
    new_order = Order(
        order_id=order_id,
        created_by_user_id=current_user.id,
        description=order_data.description,
        city_id=order_data.city_id,
        delivery_date=order_data.delivery_date,
        status=OrderStatus.NEW  # Default status
    )

    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    # Create a conversation for this order
    new_conversation = Conversation(
        customer_id=current_user.id,
        courier_id=None,  # No courier assigned yet
        order_id=new_order.id,
        status='active'
    )

    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)

    return new_order

@router.get("/", response_model=list[OrderResponse])
async def get_user_orders(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get all orders for the authenticated user.
    """
    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.created_by_user_id == current_user.id))
    orders = result.scalars().all()

    return orders

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get a specific order by order_id. The user who created the order or the assigned courier can access it.
    """
    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Allow access if user created the order OR if user is the assigned courier
    if order.created_by_user_id != current_user.id and order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this order")

    return order

@router.put("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(order_id: str, cancel_data: CancelOrderRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Cancel an order. Only the user who created the order can cancel it.
    """
    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")

    # Check if order can be cancelled
    if order.status in [OrderStatus.CANCELLED, OrderStatus.DONE]:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    # Check if order has a paid invoice
    if order.invoice and order.invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Order cannot be cancelled as it has a paid invoice. Please contact customer service.")

    # Update order
    order.status = OrderStatus.CANCELLED
    order.comments = f"{cancel_data.reason} by ID:{current_user.id} and name:{current_user.name}"
    # updated_at will be automatically updated due to onupdate=func.now()

    await db.commit()
    await db.refresh(order)

    return order

@router.put("/{order_id}/assign", response_model=OrderResponse)
async def assign_order(order_id: str, request: AssignOrderRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Assign an order to a courier. Only admins can assign orders.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to assign orders")

    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if the assigned user exists and is a courier
    result = await db.execute(select(User).where(User.id == request.assigned_to_user_id))
    assigned_user = result.scalar_one_or_none()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="Assigned user not found")
    if assigned_user.role != "Courier":
        raise HTTPException(status_code=400, detail="Assigned user must be a courier")

    # Check if order can be assigned
    if order.status in [OrderStatus.CANCELLED, OrderStatus.DONE]:
        raise HTTPException(status_code=400, detail="Order cannot be assigned")

    # Update order
    order.assigned_to_user_id = request.assigned_to_user_id
    order.status = OrderStatus.RECEIVED_BY_COURIER
    order.comments = f"Assigned to courier ID:{request.assigned_to_user_id} by admin ID:{current_user.id}"
    # updated_at will be automatically updated due to onupdate=func.now()

    # Update conversation with courier_id
    if order.conversation:
        order.conversation.courier_id = request.assigned_to_user_id
        await db.commit()

    await db.commit()
    await db.refresh(order)

    return order

@router.get("/courier/available", response_model=list[OrderResponse])
async def get_available_orders_for_courier(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get available orders for the courier in their city. Only couriers can access this.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can access available orders")

    # Get orders that are NEW and in the same city as the courier
    result = await db.execute(
        select(Order).options(selectinload(Order.invoice)).where(
            Order.status == OrderStatus.NEW,
            Order.city_id == current_user.city_id
        )
    )
    orders = result.scalars().all()

    return orders

@router.put("/{order_id}/accept", response_model=OrderResponse)
async def accept_order(order_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Accept an order by a courier. Only couriers can accept orders.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can accept orders")

    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if order is still available (NEW status)
    if order.status != OrderStatus.NEW:
        raise HTTPException(status_code=400, detail="Order is no longer available")

    # Check if order is in courier's city
    if order.city_id != current_user.city_id:
        raise HTTPException(status_code=400, detail="Order is not in your city")

    # Update order
    order.assigned_to_user_id = current_user.id
    order.status = OrderStatus.RECEIVED_BY_COURIER
    order.comments = f"Accepted by courier ID:{current_user.id} and name:{current_user.name}"
    # updated_at will be automatically updated due to onupdate=func.now()

    # Update conversation with courier_id
    if order.conversation:
        order.conversation.courier_id = current_user.id
        await db.commit()  # Commit conversation update immediately

    await db.commit()
    await db.refresh(order)

    return order

@router.get("/courier/active", response_model=list[OrderResponse])
async def get_courier_active_orders(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get active orders assigned to the courier. Only couriers can access this.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can access their active orders")

    # Get orders assigned to this courier that are not cancelled or done
    result = await db.execute(
        select(Order).options(selectinload(Order.invoice)).where(
            Order.assigned_to_user_id == current_user.id,
            Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.DONE])
        )
    )
    orders = result.scalars().all()

    return orders

@router.get("/courier/all", response_model=list[OrderResponse])
async def get_courier_all_orders(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get all orders assigned to the courier (active, completed, cancelled). Only couriers can access this.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can access their orders")

    # Get all orders assigned to this courier
    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.assigned_to_user_id == current_user.id))
    orders = result.scalars().all()

    return orders

@router.get("/courier/stats")
async def get_courier_stats(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Get courier statistics: active orders count and today's earnings from paid invoices.
    Only couriers can access this.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can access their stats")

    # Get active orders count (not cancelled or done)
    result = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.assigned_to_user_id == current_user.id,
            Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.DONE])
        )
    )
    active_orders_count = result.scalar()

    # Get today's earnings: sum of service_fee from paid invoices created today
    from datetime import datetime, time
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)

    # Sum service_fee from invoices that are paid and created today for this courier's orders
    result = await db.execute(
        select(func.sum(Invoice.service_fee)).select_from(Invoice).join(Order).where(
            Order.assigned_to_user_id == current_user.id,
            Invoice.status == InvoiceStatus.PAID,
            Invoice.created_at >= today_start,
            Invoice.created_at <= today_end
        )
    )
    todays_earnings = result.scalar() or 0

    return {
        "active_orders_count": active_orders_count,
        "todays_earnings": todays_earnings  # in cents/halaym
    }

@router.put("/{order_id}/complete", response_model=OrderResponse)
async def complete_order(order_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Mark an order as completed (DONE). Only the assigned courier can complete orders.
    When an order is completed and has a paid invoice, add courier fee to courier's wallet.
    """
    if current_user.role != "Courier":
        raise HTTPException(status_code=403, detail="Only couriers can complete orders")

    result = await db.execute(select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if order is assigned to this courier
    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    # Check if order can be completed
    if order.status in [OrderStatus.CANCELLED, OrderStatus.DONE]:
        raise HTTPException(status_code=400, detail="Order cannot be completed")

    # Check if order has a paid invoice
    if not order.invoice or order.invoice.status != "paid":
        raise HTTPException(status_code=400, detail="Order cannot be completed - invoice not paid")

    # Get courier's wallet
    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    courier_wallet = result.scalar_one_or_none()
    if not courier_wallet:
        raise HTTPException(status_code=404, detail="Courier wallet not found")

    try:
        # Record balance before addition
        balance_before = courier_wallet.balance

        # Add courier fee to wallet
        courier_fee = order.invoice.courier_fee
        courier_wallet.balance += courier_fee
        courier_wallet.updated_at = datetime.utcnow()

        # Mark order as done
        order.status = OrderStatus.DONE
        order.comments = f"Completed by courier ID:{current_user.id} and name:{current_user.name}"
        order.updated_at = datetime.utcnow()

        # Create courier balance addition record
        # Find the payment that was made for this invoice
        result = await db.execute(
            select(Payment).where(
                Payment.invoice_id == order.invoice.id,
                Payment.status == "completed"
            )
        )
        payment = result.scalar_one_or_none()

        if payment:
            courier_balance_addition = CourierBalanceAddition(
                invoice_id=order.invoice.id,
                order_id=order.id,
                user_id=payment.user_id,  # User who paid
                payment_method=payment.payment_method,
                balance_before=balance_before,
                amount_to_add=courier_fee
            )
            db.add(courier_balance_addition)

        await db.commit()
        await db.refresh(order)

        return order

    except Exception as e:
        await db.rollback()
        print(f"Error completing order: {e}")
        raise HTTPException(status_code=500, detail="-/+ .7# #+F'! %CE'D 'D7D(. J1,I 'DE-'HD) E1) #.1I.")

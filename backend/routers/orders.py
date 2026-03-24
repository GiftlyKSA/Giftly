from datetime import datetime, time, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select, desc
from database import get_db
from models import (Order, City, User, OrderStatus, Conversation, CourierBalanceAddition,
                    Invoice, Wallet, Payment, PaymentMethod, InvoiceStatus, CourierProfile, OrderImage)
from schemas import CreateOrder, OrderResponse, CancelOrderRequest, AssignOrderRequest
from auth import get_current_user
from websocket_events import emit_order_status_change
from storage_client import upload_image
from enums import ImageType, UserRole, ConversationStatus
import mimetypes

router = APIRouter()


@router.post("/", response_model=OrderResponse)
async def create_order(
    description: str = Form(None),
    city_id: int = Form(...),
    delivery_date: datetime = Form(...),
    image1: UploadFile = File(None),
    image2: UploadFile = File(None),
    image3: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new order with optional image uploads. Only authenticated users can create orders.
    City and delivery_date are mandatory, description is optional.
    Up to 3 images can be uploaded, each max 15MB, only image files allowed.
    """
    result = await db.execute(select(City).where(City.id == city_id))
    city = result.scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=400, detail="Invalid city ID")

    if description is not None and len(description.strip()) == 0:
        description = None

    images = [image1, image2, image3]
    uploaded_images = []

    for i, img in enumerate(images, 1):
        if img is not None:
            if img.size > 15 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"Image {i} exceeds 15MB size limit")

            allowed_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']
            if img.content_type not in allowed_mime_types:
                file_ext = img.filename.split('.')[-1].lower() if '.' in img.filename else ''
                if file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Image {i}: Only image files are allowed (JPEG, PNG, GIF, WebP, SVG)"
                    )
            uploaded_images.append((i, img))

    result = await db.execute(select(func.max(Order.id)))
    max_id = result.scalar() or 0
    order_id = f"ORDR-{100000 + max_id + 1}"

    new_order = Order(
        order_id=order_id,
        created_by_user_id=current_user.id,
        description=description,
        city_id=city_id,
        delivery_date=delivery_date,
        status=OrderStatus.NEW,
    )
    db.add(new_order)
    await db.commit()

    image_urls = {}
    for img_num, img_file in uploaded_images:
        try:
            result = await upload_image(
                user_id=current_user.id,
                username=current_user.name or f"user_{current_user.id}",
                image_type=ImageType.ORDER,
                image=img_file
            )
            image_urls[f"image{img_num}_url"] = result["url"]
        except Exception as e:
            await db.delete(new_order)
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to upload image {img_num}: {str(e)}")

    order_images = OrderImage(order_id=new_order.id, **image_urls)
    db.add(order_images)
    await db.commit()

    new_conversation = Conversation(
        customer_id=current_user.id,
        courier_id=None,
        order_id=new_order.id,
        status=ConversationStatus.ACTIVE,
    )
    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)

    if new_order.description and new_order.description.strip():
        from websocket_events import emit_chat_message
        from models import Message

        initial_message = Message(
            conversation_id=new_conversation.id,
            sender_id=current_user.id,
            content=new_order.description,
            message_type='text',
        )
        db.add(initial_message)
        await db.commit()
        await db.refresh(initial_message)

        await emit_chat_message(new_conversation.id, {
            "id": initial_message.id,
            "conversation_id": initial_message.conversation_id,
            "sender_id": initial_message.sender_id,
            "content": initial_message.content,
            "message_type": initial_message.message_type,
            "sent_at": initial_message.sent_at.isoformat()
        }, db)

    image_messages = []
    for img_num, (orig_num, img_file) in enumerate(uploaded_images, 1):
        from models import Message
        image_message = Message(
            conversation_id=new_conversation.id,
            sender_id=current_user.id,
            content=f"صورة الطلب {img_num}",
            message_type='image',
            image_data=image_urls[f"image{orig_num}_url"],
        )
        db.add(image_message)
        image_messages.append(image_message)

    if image_messages:
        await db.commit()
        for image_message in image_messages:
            await db.refresh(image_message)
            from websocket_events import emit_chat_message
            await emit_chat_message(new_conversation.id, {
                "id": image_message.id,
                "conversation_id": image_message.conversation_id,
                "sender_id": image_message.sender_id,
                "content": image_message.content,
                "message_type": image_message.message_type,
                "image_data": image_message.image_data,
                "sent_at": image_message.sent_at.isoformat()
            }, db)

    await emit_order_status_change(new_order.id, new_order.status.value)

    from websocket_manager import manager
    await manager.broadcast_to_room({
        "event": "new_order",
        "data": {
            "order_id": new_order.order_id,
            "id": new_order.id,
            "description": new_order.description,
            "city_id": new_order.city_id,
            "delivery_date": new_order.delivery_date.isoformat() if new_order.delivery_date else None,
            "created_by_user_id": new_order.created_by_user_id,
        }
    }, f"couriers_city_{new_order.city_id}")

    return {
        "id": new_order.id,
        "order_id": new_order.order_id,
        "created_by_user_id": new_order.created_by_user_id,
        "assigned_to_user_id": new_order.assigned_to_user_id,
        "description": new_order.description,
        "creation_date": new_order.creation_date,
        "delivery_date": new_order.delivery_date,
        "status": new_order.status,
        "comments": new_order.comments,
        "updated_at": new_order.updated_at,
        "city_id": new_order.city_id,
        "invoice": None,
    }


@router.get("/", response_model=list[OrderResponse])
async def get_user_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all orders for the authenticated user."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice))
        .where(Order.created_by_user_id == current_user.id)
        .order_by(Order.creation_date.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific order by order_id. The creator or assigned courier can access it."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice), selectinload(Order.conversation), selectinload(Order.created_by_user))
        .where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.created_by_user_id != current_user.id and order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this order")

    return order


@router.put("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    cancel_data: CancelOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an order. Only the creator can cancel it."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice), selectinload(Order.conversation), selectinload(Order.created_by_user))
        .where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")

    if order.status in [OrderStatus.CANCELLED, OrderStatus.DONE]:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    if order.invoice and order.invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=400,
            detail="Order cannot be cancelled as it has a paid invoice. Please contact customer service.",
        )

    order.status = OrderStatus.CANCELLED
    order.comments = f"{cancel_data.reason} by ID:{current_user.id} and name:{current_user.name}"
    await db.commit()
    await db.refresh(order)

    await emit_order_status_change(order.id, order.status.value)
    return order


@router.put("/{order_id}/assign", response_model=OrderResponse)
async def assign_order(
    order_id: str,
    request: AssignOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign an order to a courier. Admin use only."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice), selectinload(Order.conversation), selectinload(Order.created_by_user))
        .where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    result = await db.execute(select(User).where(User.id == request.assigned_to_user_id))
    assigned_user = result.scalar_one_or_none()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="Assigned user not found")
    if assigned_user.role != UserRole.COURIER:
        raise HTTPException(status_code=400, detail="Assigned user must be a courier")

    if order.status in [OrderStatus.CANCELLED, OrderStatus.DONE]:
        raise HTTPException(status_code=400, detail="Order cannot be assigned")

    order.assigned_to_user_id = request.assigned_to_user_id
    order.status = OrderStatus.RECEIVED_BY_COURIER
    order.comments = f"Assigned to courier ID:{request.assigned_to_user_id} by admin ID:{current_user.id}"

    if order.conversation:
        order.conversation.courier_id = request.assigned_to_user_id

    await db.commit()
    await db.refresh(order)
    await emit_order_status_change(order.id, order.status.value)
    return order


@router.get("/courier/available", response_model=list[OrderResponse])
async def get_available_orders_for_courier(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get available orders for the courier in their city. Couriers only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can access available orders")

    result = await db.execute(select(CourierProfile).where(CourierProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Courier profile not found")
    if not profile.is_approved:
        raise HTTPException(status_code=403, detail="Your account is not yet approved")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice))
        .where(
            Order.status == OrderStatus.NEW,
            Order.assigned_to_user_id.is_(None),
            Order.city_id == profile.city_id,
        )
        .order_by(Order.creation_date.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.put("/{order_id}/accept", response_model=OrderResponse)
async def accept_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept an order by a courier. Couriers only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can accept orders")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice), selectinload(Order.conversation), selectinload(Order.created_by_user))
        .where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatus.NEW:
        raise HTTPException(status_code=400, detail="Order is no longer available")

    result = await db.execute(select(CourierProfile).where(CourierProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Courier profile not found")

    # Guard: only approved, available couriers can accept
    if not profile.is_approved:
        raise HTTPException(status_code=403, detail="Your account is not yet approved")
    if not profile.is_available:
        raise HTTPException(status_code=403, detail="You are currently marked as unavailable")

    if order.city_id != profile.city_id:
        raise HTTPException(status_code=400, detail="Order is not in your city")

    order.assigned_to_user_id = current_user.id
    order.status = OrderStatus.RECEIVED_BY_COURIER
    order.comments = f"Accepted by courier ID:{current_user.id} and name:{current_user.name}"

    if order.conversation:
        order.conversation.courier_id = current_user.id

    await db.commit()
    await db.refresh(order)

    from websocket_events import emit_chat_message
    from models import Message

    customer_name = order.created_by_user.name if order.created_by_user else "عميلنا الكريم"
    welcome_message = Message(
        conversation_id=order.conversation.id,
        sender_id=current_user.id,
        content=f"أهلاً وسهلاً {customer_name}\nاستلمت طلبك الآن وراح أبدأ بالتنسيق حسب التفاصيل.",
        message_type='text',
    )
    db.add(welcome_message)
    await db.commit()
    await db.refresh(welcome_message)

    await emit_chat_message(order.conversation.id, {
        "id": welcome_message.id,
        "conversation_id": welcome_message.conversation_id,
        "sender_id": welcome_message.sender_id,
        "content": welcome_message.content,
        "message_type": welcome_message.message_type,
        "sent_at": welcome_message.sent_at.isoformat()
    }, db)

    await emit_order_status_change(order.id, order.status.value)

    from websocket_manager import manager
    await manager.send_to_user(order.created_by_user_id, {
        "event": "chat_available",
        "data": {
            "order_id": order.order_id,
            "conversation_id": order.conversation.id if order.conversation else None,
            "courier_id": current_user.id,
            "courier_name": current_user.name,
        }
    })

    return order


@router.post("/{order_id}/confirm-delivery")
async def confirm_delivery(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Customer confirms delivery, allowing the courier to mark the order DONE."""
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the customer who placed this order can confirm delivery")

    if order.status == OrderStatus.DONE:
        raise HTTPException(status_code=400, detail="Order is already completed")
    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Order is cancelled")

    order.customer_confirmed = True
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Delivery confirmed. The courier can now mark the order as done."}


@router.get("/courier/active", response_model=list[OrderResponse])
async def get_courier_active_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get active orders assigned to the courier. Couriers only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can access their active orders")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice))
        .where(
            Order.assigned_to_user_id == current_user.id,
            Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.DONE]),
        )
        .order_by(Order.creation_date.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/courier/all", response_model=list[OrderResponse])
async def get_courier_all_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all orders assigned to the courier. Couriers only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can access their orders")

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.invoice))
        .where(Order.assigned_to_user_id == current_user.id)
        .order_by(Order.creation_date.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/courier/stats")
async def get_courier_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get courier statistics: active orders count and today's earnings. Couriers only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can access their stats")

    result = await db.execute(
        select(func.count()).select_from(Order).where(
            Order.assigned_to_user_id == current_user.id,
            Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.DONE]),
        )
    )
    active_orders_count = result.scalar()

    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min)
    today_end = datetime.combine(datetime.now(timezone.utc).date(), time.max)

    result = await db.execute(
        select(func.sum(Invoice.service_fee)).select_from(Invoice).join(Order).where(
            Order.assigned_to_user_id == current_user.id,
            Invoice.status == InvoiceStatus.PAID,
            Invoice.created_at >= today_start,
            Invoice.created_at <= today_end,
        )
    )
    todays_earnings = result.scalar() or 0

    return {"active_orders_count": active_orders_count, "todays_earnings": todays_earnings}


@router.put("/{order_id}/complete", response_model=OrderResponse)
async def complete_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an order as DONE. Assigned courier only. Customer must confirm delivery first."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can complete orders")

    result = await db.execute(
        select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    if order.status in [OrderStatus.CANCELLED, OrderStatus.DONE]:
        raise HTTPException(status_code=400, detail="Order cannot be completed")

    if not order.customer_confirmed:
        raise HTTPException(status_code=400, detail="Customer has not confirmed delivery yet")

    if not order.invoice or order.invoice.status != InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Order cannot be completed — invoice not paid")

    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    courier_wallet = result.scalar_one_or_none()
    if not courier_wallet:
        raise HTTPException(status_code=404, detail="Courier wallet not found")

    try:
        balance_before = courier_wallet.balance
        courier_fee = order.invoice.courier_fee
        courier_wallet.balance += courier_fee
        courier_wallet.updated_at = datetime.now(timezone.utc)

        order.status = OrderStatus.DONE
        order.comments = f"Completed by courier ID:{current_user.id} and name:{current_user.name}"
        order.updated_at = datetime.now(timezone.utc)

        result = await db.execute(
            select(Payment).where(
                Payment.invoice_id == order.invoice.id,
                Payment.status == "completed",
            )
        )
        payment = result.scalar_one_or_none()

        if payment:
            courier_balance_addition = CourierBalanceAddition(
                invoice_id=order.invoice.id,
                order_id=order.id,
                user_id=payment.user_id,
                payment_method=payment.payment_method,
                balance_before=balance_before,
                amount_to_add=courier_fee,
            )
            db.add(courier_balance_addition)

        await db.commit()
        await db.refresh(order)

        await emit_order_status_change(order.id, order.status.value)
        return order

    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء إتمام الطلب. يرجى المحاولة مرة أخرى.")


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update order status. Assigned courier only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(status_code=403, detail="Only couriers can update order status")

    result = await db.execute(
        select(Order).options(selectinload(Order.invoice)).where(Order.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Order is not assigned to you")

    valid_statuses = ["received by courier", "in_progress", "ready_for_delivery", "out_for_delivery"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid statuses: {', '.join(valid_statuses)}")

    order.status = status
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(order)

    await emit_order_status_change(order.id, order.status)
    return order

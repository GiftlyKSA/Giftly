from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import desc, select
from database import get_db
from models import Conversation, Message, User, Order
from schemas import CreateConversationRequest, ConversationResponse, SendMessageRequest, MessageResponse
from auth import get_current_user
from typing import List
import base64

router = APIRouter()

@router.post("/conversations", response_model=ConversationResponse)
async def create_or_get_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation or return existing one between current user and other user.
    The current user and other user must be customer and courier respectively.
    """
    # Get the other user
    result = await db.execute(select(User).where(User.id == request.other_user_id))
    other_user = result.scalar_one_or_none()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Determine roles: current user should be customer, other user should be courier
    if current_user.role not in ['Customer', 'Courier'] or other_user.role not in ['Customer', 'Courier']:
        raise HTTPException(status_code=400, detail="Invalid user roles for conversation")

    # Ensure one is customer and one is courier
    if current_user.role == other_user.role:
        raise HTTPException(status_code=400, detail="Cannot create conversation between users of same role")

    # Determine customer and courier IDs
    if current_user.role == 'Customer':
        customer_id = current_user.id
        courier_id = other_user.id
    else:
        customer_id = other_user.id
        courier_id = current_user.id

    # Check if conversation already exists
    result = await db.execute(
        select(Conversation).where(
            Conversation.customer_id == customer_id,
            Conversation.courier_id == courier_id
        )
    )
    existing_conversation = result.scalar_one_or_none()

    if existing_conversation:
        return existing_conversation

    # Create new conversation
    new_conversation = Conversation(
        customer_id=customer_id,
        courier_id=courier_id,
        status='active'
    )

    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)

    return new_conversation

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated messages for a conversation.
    Only participants of the conversation can access it.
    """
    # Get conversation
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    # Get messages with pagination, ordered by sent_at desc (newest first)
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.sent_at))
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()

    # Reverse to get chronological order (oldest first)
    messages = list(messages)
    messages.reverse()

    return messages

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message in a conversation.
    Only participants of the conversation can send messages.
    """
    # Get conversation
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to send messages in this conversation")

    # Validate message type
    if request.message_type not in ['text', 'invoice', 'image']:
        raise HTTPException(status_code=400, detail="Invalid message type")

    # For invoice messages, ensure all invoice fields are provided
    if request.message_type == 'invoice':
        required_fields = ['invoice_description', 'invoice_gift_price', 'invoice_service_fee', 'invoice_delivery_fee', 'invoice_total']
        for field in required_fields:
            if getattr(request, field) is None:
                raise HTTPException(status_code=400, detail=f"{field} is required for invoice messages")

    # For image messages, ensure image_data is provided
    if request.message_type == 'image':
        if not request.image_data:
            raise HTTPException(status_code=400, detail="image_data is required for image messages")

    # Create message
    new_message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=request.content,
        message_type=request.message_type,
        invoice_description=request.invoice_description,
        invoice_gift_price=request.invoice_gift_price,
        invoice_service_fee=request.invoice_service_fee,
        invoice_delivery_fee=request.invoice_delivery_fee,
        invoice_total=request.invoice_total,
        image_data=request.image_data
    )

    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)

    return new_message

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all conversations for the current user.
    """
    result = await db.execute(
        select(Conversation).where(
            (Conversation.customer_id == current_user.id) | (Conversation.courier_id == current_user.id)
        ).order_by(desc(Conversation.created_at))
    )
    conversations = result.scalars().all()

    return conversations

@router.get("/conversations/by-order/{order_id}", response_model=ConversationResponse)
async def get_conversation_by_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversation for a specific order. Only participants can access it.
    """
    result = await db.execute(select(Conversation).where(Conversation.order_id == order_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization - user must be customer or courier for this order
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    return conversation

@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_status(
    conversation_id: int,
    status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation status. Only participants can update the conversation.
    Valid statuses: active, inactive
    """
    # Get conversation
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization - user must be customer or courier for this conversation
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to update this conversation")

    # Validate status
    if status not in ['active', 'inactive']:
        raise HTTPException(status_code=400, detail="Invalid status. Valid statuses: active, inactive")

    # Update conversation status
    conversation.status = status
    await db.commit()
    await db.refresh(conversation)

    return conversation

@router.get("/messages/{message_id}/image")
async def get_message_image(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get image data for a message. Only participants of the conversation can access it.
    """
    # Get message
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Get conversation to check authorization
    result = await db.execute(select(Conversation).where(Conversation.id == message.conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this message")

    # Check if message has image data
    if not message.image_data:
        raise HTTPException(status_code=404, detail="No image data found for this message")

    # Decode base64 and return as image
    try:
        # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
        if message.image_data.startswith('data:'):
            # Extract the base64 part after the comma
            base64_data = message.image_data.split(',')[1]
        else:
            base64_data = message.image_data

        image_bytes = base64.b64decode(base64_data)

        # Determine content type from base64 data (simple detection)
        if base64_data.startswith('/9j/'):  # JPEG
            content_type = 'image/jpeg'
        elif base64_data.startswith('iVBOR'):  # PNG
            content_type = 'image/png'
        else:
            content_type = 'image/jpeg'  # Default

        return Response(content=image_bytes, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error processing image data")

@router.get("/orders/{order_id}/images/{image_number}")
async def get_order_image(
    order_id: int,
    image_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get image data for an order. Only the order creator can access it.
    image_number should be 1, 2, or 3
    """
    if image_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Invalid image number. Must be 1, 2, or 3")

    # Get order
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check authorization - only order creator can access
    if current_user.id != order.created_by_user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this order")

    # Get the appropriate image data
    image_data = getattr(order, f'image{image_number}_data')
    if not image_data:
        raise HTTPException(status_code=404, detail=f"No image data found for image {image_number}")

    # Decode base64 and return as image
    try:
        # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
        if image_data.startswith('data:'):
            # Extract the base64 part after the comma
            base64_data = image_data.split(',')[1]
        else:
            base64_data = image_data

        image_bytes = base64.b64decode(base64_data)

        # Determine content type from base64 data (simple detection)
        if base64_data.startswith('/9j/'):  # JPEG
            content_type = 'image/jpeg'
        elif base64_data.startswith('iVBOR'):  # PNG
            content_type = 'image/png'
        else:
            content_type = 'image/jpeg'  # Default

        return Response(content=image_bytes, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error processing image data")

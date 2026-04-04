from typing import List

from auth import get_current_user
from utils.database.database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Conversation, Message, Order, User
from schemas import ConversationResponse, CreateConversationRequest, MessageResponse
from utils.clients.storage_client import upload_media

router = APIRouter()


@router.post("/conversations", response_model=ConversationResponse)
async def create_or_get_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
    if current_user.role not in ["Customer", "Courier"] or other_user.role not in [
        "Customer",
        "Courier",
    ]:
        raise HTTPException(
            status_code=400, detail="Invalid user roles for conversation"
        )

    # Ensure one is customer and one is courier
    if current_user.role == other_user.role:
        raise HTTPException(
            status_code=400,
            detail="Cannot create conversation between users of same role",
        )

    # Determine customer and courier IDs
    if current_user.role == "Customer":
        customer_id = current_user.id
        courier_id = other_user.id
    else:
        customer_id = other_user.id
        courier_id = current_user.id

    # Check if conversation already exists
    result = await db.execute(
        select(Conversation).where(
            Conversation.customer_id == customer_id,
            Conversation.courier_id == courier_id,
        )
    )
    existing_conversation = result.scalar_one_or_none()

    if existing_conversation:
        return existing_conversation

    # Create new conversation
    new_conversation = Conversation(
        customer_id=customer_id, courier_id=courier_id, status="active"
    )

    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)

    return new_conversation


@router.get(
    "/conversations/{conversation_id}/messages", response_model=List[MessageResponse]
)
async def get_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated messages for a conversation.
    Only participants of the conversation can access it.
    """
    # Get conversation
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this conversation"
        )

    # Get messages with pagination, ordered by sent_at desc (newest first)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.sent_at))
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()

    # Reverse to get chronological order (oldest first)
    messages = list(messages)
    messages.reverse()

    return messages


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse
)
async def send_message(
    conversation_id: int,
    content: str = Form(...),
    message_type: str = Form("text"),
    media_type: str = Form(None),
    invoice_description: str = Form(None),
    invoice_gift_price: int = Form(None),
    invoice_service_fee: int = Form(None),
    invoice_delivery_fee: int = Form(None),
    invoice_total: int = Form(None),
    media_file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message in a conversation with optional media upload.
    Only participants of the conversation can send messages.
    Supports text, invoice, image, video, and system messages.
    """
    # Get conversation
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to send messages in this conversation",
        )

    # Validate message type
    valid_message_types = ["text", "invoice", "image", "video", "system"]
    if message_type not in valid_message_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid message type. Valid types: {', '.join(valid_message_types)}",
        )

    # Validate media file if provided
    media_url = None
    if media_file is not None:
        # Check file size limits
        if (
            message_type == "image" and media_file.size > 15 * 1024 * 1024
        ):  # 15MB for images
            raise HTTPException(
                status_code=400, detail="Image file size exceeds 15MB limit"
            )
        elif (
            message_type == "video" and media_file.size > 100 * 1024 * 1024
        ):  # 100MB for videos
            raise HTTPException(
                status_code=400, detail="Video file size exceeds 100MB limit"
            )

        # Check file type
        allowed_image_types = [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/svg+xml",
        ]
        allowed_video_types = [
            "video/mp4",
            "video/avi",
            "video/mov",
            "video/mkv",
            "video/webm",
        ]
        allowed_image_exts = ["jpg", "jpeg", "png", "gif", "webp", "svg"]
        allowed_video_exts = ["mp4", "avi", "mov", "mkv", "webm"]

        file_ext = (
            media_file.filename.split(".")[-1].lower()
            if "." in media_file.filename
            else ""
        )

        if message_type == "image":
            if (
                media_file.content_type not in allowed_image_types
                and file_ext not in allowed_image_exts
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Only image files are allowed (JPEG, PNG, GIF, WebP, SVG)",
                )
        elif message_type == "video":
            if (
                media_file.content_type not in allowed_video_types
                and file_ext not in allowed_video_exts
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Only video files are allowed (MP4, AVI, MOV, MKV, WebM)",
                )

        # Upload media file
        try:
            upload_result = await upload_media(
                user_id=current_user.id,
                username=current_user.name or f"user_{current_user.id}",
                media_type=message_type,  # 'image' or 'video'
                media=media_file,
            )
            media_url = upload_result["url"]
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to upload media file: {str(e)}"
            )

    # For invoice messages, ensure all invoice fields are provided
    if message_type == "invoice":
        required_fields = [
            "invoice_description",
            "invoice_gift_price",
            "invoice_service_fee",
            "invoice_delivery_fee",
            "invoice_total",
        ]
        for field in required_fields:
            if locals()[field] is None:
                raise HTTPException(
                    status_code=400, detail=f"{field} is required for invoice messages"
                )

    # For media messages, ensure media_url is provided
    if message_type in ["image", "video"]:
        if not media_url:
            raise HTTPException(
                status_code=400,
                detail=f"Media file is required for {message_type} messages",
            )

    # Determine sender_id (None for system messages)
    sender_id = None if message_type == "system" else current_user.id

    # Create message
    new_message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
        message_type=message_type,
        media_type=media_type,
        invoice_description=invoice_description,
        invoice_gift_price=invoice_gift_price,
        invoice_service_fee=invoice_service_fee,
        invoice_delivery_fee=invoice_delivery_fee,
        invoice_total=invoice_total,
        media_url=media_url,
    )

    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)

    return new_message


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get all conversations for the current user.
    """
    result = await db.execute(
        select(Conversation)
        .where(
            (Conversation.customer_id == current_user.id)
            | (Conversation.courier_id == current_user.id)
        )
        .order_by(desc(Conversation.created_at))
    )
    conversations = result.scalars().all()

    return conversations


@router.get("/conversations/by-order/{order_id}", response_model=ConversationResponse)
async def get_conversation_by_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get conversation for a specific order. Only participants can access it.
    """
    result = await db.execute(
        select(Conversation).where(Conversation.order_id == order_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization - user must be customer or courier for this order
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this conversation"
        )

    return conversation


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_status(
    conversation_id: int,
    status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update conversation status. Only participants can update the conversation.
    Valid statuses: active, inactive
    """
    # Get conversation
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization - user must be customer or courier for this conversation
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this conversation"
        )

    # Validate status
    if status not in ["active", "inactive"]:
        raise HTTPException(
            status_code=400, detail="Invalid status. Valid statuses: active, inactive"
        )

    # Update conversation status
    conversation.status = status
    await db.commit()
    await db.refresh(conversation)

    return conversation


@router.get("/messages/{message_id}/media")
async def get_message_media(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get media URL for a message. Only participants of the conversation can access it.
    Returns the media URL directly since media is stored on Cloudflare R2.
    """
    # Get message
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Get conversation to check authorization
    result = await db.execute(
        select(Conversation).where(Conversation.id == message.conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this message"
        )

    # Check if message has media URL
    if not message.media_url:
        raise HTTPException(status_code=404, detail="No media found for this message")

    # Return the media URL directly
    return {"media_url": message.media_url, "media_type": message.media_type}


@router.get("/orders/{order_id}/images/{image_number}")
async def get_order_image(
    order_id: int,
    image_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get image URL for an order. Only the order creator can access it.
    image_number should be 1, 2, or 3
    """
    if image_number not in [1, 2, 3]:
        raise HTTPException(
            status_code=400, detail="Invalid image number. Must be 1, 2, or 3"
        )

    # Get order with images
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check authorization - only order creator can access
    if current_user.id != order.created_by_user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this order"
        )

    # Get the order images
    result = await db.execute(select(OrderImage).where(OrderImage.order_id == order_id))
    order_images = result.scalar_one_or_none()
    if not order_images:
        raise HTTPException(status_code=404, detail="No images found for this order")

    # Get the appropriate image URL
    image_url = getattr(order_images, f"image{image_number}_url")
    if not image_url:
        raise HTTPException(
            status_code=404, detail=f"No image found for image {image_number}"
        )

    # Return the image URL directly
    return {"image_url": image_url}

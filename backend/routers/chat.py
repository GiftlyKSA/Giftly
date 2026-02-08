from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db, get_db_sync
from models import Conversation, Message, User
from schemas import CreateConversationRequest, ConversationResponse, SendMessageRequest, MessageResponse
from auth import get_current_user
from typing import List

router = APIRouter()

@router.post("/conversations", response_model=ConversationResponse)
def create_or_get_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_sync)
):
    """
    Create a new conversation or return existing one between current user and other user.
    The current user and other user must be customer and courier respectively.
    """
    # Get the other user
    other_user = db.query(User).filter(User.id == request.other_user_id).first()
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
    existing_conversation = db.query(Conversation).filter(
        Conversation.customer_id == customer_id,
        Conversation.courier_id == courier_id
    ).first()

    if existing_conversation:
        return existing_conversation

    # Create new conversation
    new_conversation = Conversation(
        customer_id=customer_id,
        courier_id=courier_id,
        status='active'
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    return new_conversation

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_sync)
):
    """
    Get paginated messages for a conversation.
    Only participants of the conversation can access it.
    """
    # Get conversation
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    # Get messages with pagination, ordered by sent_at desc (newest first)
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(desc(Message.sent_at)).offset(skip).limit(limit).all()

    # Reverse to get chronological order (oldest first)
    messages.reverse()

    return messages

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def send_message(
    conversation_id: int,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_sync)
):
    """
    Send a message in a conversation.
    Only participants of the conversation can send messages.
    """
    # Get conversation
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to send messages in this conversation")

    # Validate message type
    if request.message_type not in ['text', 'invoice']:
        raise HTTPException(status_code=400, detail="Invalid message type")

    # For invoice messages, ensure all invoice fields are provided
    if request.message_type == 'invoice':
        required_fields = ['invoice_description', 'invoice_gift_price', 'invoice_service_fee', 'invoice_delivery_fee', 'invoice_total']
        for field in required_fields:
            if getattr(request, field) is None:
                raise HTTPException(status_code=400, detail=f"{field} is required for invoice messages")

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
        invoice_total=request.invoice_total
    )

    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return new_message

@router.get("/conversations", response_model=List[ConversationResponse])
def get_user_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_sync)
):
    """
    Get all conversations for the current user.
    """
    conversations = db.query(Conversation).filter(
        (Conversation.customer_id == current_user.id) | (Conversation.courier_id == current_user.id)
    ).order_by(desc(Conversation.created_at)).all()

    return conversations

@router.get("/conversations/by-order/{order_id}", response_model=ConversationResponse)
def get_conversation_by_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_sync)
):
    """
    Get conversation for a specific order. Only participants can access it.
    """
    conversation = db.query(Conversation).filter(Conversation.order_id == order_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check authorization - user must be customer or courier for this order
    if current_user.id not in [conversation.customer_id, conversation.courier_id]:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")

    return conversation

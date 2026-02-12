from sqladmin import Admin, ModelView
from database import engine
from models import User, City, Order, Invoice, Conversation, Message, Wallet, Payment, PaymentMethod, PaymentStatus, Promocode
from auth import verify_password
from sqlalchemy.orm import Session
from database import AsyncSessionLocal as SessionLocal
from fastapi import Request, HTTPException, status
import base64
from wtforms import DateField
from datetime import date

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.phone_number, User.email, User.name, User.date_of_birth, User.is_verified, User.otp, User.otp_created_at, User.is_admin, User.role, User.admin_username, User.admin_password_hash, User.city]
    column_searchable_list = [User.phone_number, User.email, User.name]
    column_filters = [User.is_verified, User.role, User.is_admin]

    column_choices = {
        User.role: {
            'Customer': 'Customer',
            'Admin': 'Admin',
            'Courier': 'Courier'
        }
    }

    form_overrides = {
        'date_of_birth': DateField
    }

    form_args = {
        'date_of_birth': {
            'format': '%Y-%m-%d'
        }
    }

class CityAdmin(ModelView, model=City):
    __name__ = "Cities"
    column_list = [City.id, City.name, City.icon, City.active]
    column_searchable_list = [City.name]
    column_filters = [City.active]

class OrderAdmin(ModelView, model=Order):
    column_list = [Order.id, Order.order_id, Order.created_by_user, Order.assigned_to_user, Order.description, Order.creation_date, Order.delivery_date, Order.status, Order.comments, Order.updated_at, Order.city]
    column_searchable_list = [Order.order_id, Order.description]
    column_filters = [Order.status, Order.city]
    form_excluded_columns = [Order.creation_date, Order.updated_at]

    column_choices = {
        Order.status: {
            'new': 'New',
            'received by courier': 'Received by Courier',
            'paid': 'Paid',
            'in progress to do': 'In Progress to Do',
            'cancelled': 'Cancelled',
            'done': 'Done',
            'in progress to deliver': 'In Progress to Deliver'
        }
    }

class InvoiceAdmin(ModelView, model=Invoice):
    column_list = [Invoice.id, Invoice.invoice_id, Invoice.order, Invoice.full_amount, Invoice.service_fee, Invoice.order_only_price, Invoice.courier_fee, Invoice.status, Invoice.description, Invoice.comment, Invoice.sent_to_user_via_email, Invoice.sent_at, Invoice.due_date, Invoice.tax_amount, Invoice.discount_amount, Invoice.promocode, Invoice.created_at, Invoice.updated_at]
    column_searchable_list = [Invoice.invoice_id]
    column_filters = [Invoice.status, Invoice.sent_to_user_via_email]
    form_excluded_columns = [Invoice.created_at, Invoice.updated_at]

    column_choices = {
        Invoice.status: {
            'new': 'New',
            'paid': 'Paid',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded',
            'other': 'Other'
        }
    }

class ConversationAdmin(ModelView, model=Conversation):
    column_list = [Conversation.id, Conversation.customer, Conversation.courier, Conversation.status, Conversation.created_at]
    column_searchable_list = [Conversation.customer, Conversation.courier]
    column_filters = [Conversation.status]
    form_excluded_columns = [Conversation.created_at]

    column_choices = {
        Conversation.status: {
            'active': 'Active',
            'inactive': 'Inactive',
            'closed': 'Closed'
        }
    }

class MessageAdmin(ModelView, model=Message):
    column_list = [Message.id, Message.conversation, Message.sender, Message.content, Message.sent_at, Message.message_type]
    column_searchable_list = [Message.content]
    column_filters = [Message.message_type, Message.conversation, Message.sender]
    form_excluded_columns = [Message.sent_at]

    column_choices = {
        Message.message_type: {
            'text': 'Text',
            'invoice': 'Invoice'
        }
    }

class WalletAdmin(ModelView, model=Wallet):
    column_list = [Wallet.id, Wallet.user, Wallet.balance, Wallet.created_at, Wallet.updated_at]
    column_searchable_list = [Wallet.user]
    column_filters = [Wallet.user]
    form_excluded_columns = [Wallet.created_at, Wallet.updated_at]

class PaymentAdmin(ModelView, model=Payment):
    column_list = [Payment.id, Payment.invoice, Payment.user, Payment.amount, Payment.payment_method, Payment.status, Payment.transaction_id, Payment.payment_date, Payment.created_at, Payment.updated_at]
    column_searchable_list = [Payment.transaction_id]
    column_filters = [Payment.status, Payment.payment_method, Payment.user, Payment.invoice]
    form_excluded_columns = [Payment.created_at, Payment.updated_at]

    column_choices = {
        Payment.payment_method: {
            'wallet': 'Wallet',
            'credit_card': 'Credit Card',
            'apple_pay': 'Apple Pay',
            'mada': 'Mada'
        },
        Payment.status: {
            'pending': 'Pending',
            'completed': 'Completed',
            'failed': 'Failed',
            'refunded': 'Refunded'
        }
    }

class PromocodeAdmin(ModelView, model=Promocode):
    column_list = [Promocode.id, Promocode.name, Promocode.code, Promocode.percentage, Promocode.max_value, Promocode.minimum_order_value, Promocode.usage_limit, Promocode.usage_count, Promocode.valid_until, Promocode.active, Promocode.applicable_to, Promocode.created_at]
    column_searchable_list = [Promocode.name, Promocode.code]
    column_filters = [Promocode.active, Promocode.applicable_to]
    form_excluded_columns = [Promocode.created_at, Promocode.updated_at]

    column_choices = {
        Promocode.applicable_to: {
            'order_total': 'Order Total',
            'delivery_fee': 'Delivery Fee',
            'service_fee': 'Service Fee'
        }
    }

def authenticate_admin_request(request: Request) -> bool:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return False

    try:
        encoded_credentials = auth_header.split(" ")[1]
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded_credentials.split(":", 1)

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.admin_username == username, User.is_admin == True).first()
            print(f"user is {user}") 
            
            if not user:
                return False
            return verify_password(password, user.admin_password_hash)
        finally:
            db.close()
    except:
        return False

# We'll create the admin instance in main.py after the app is created

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

from database import SessionLocal
from models import User, Conversation, JWTToken
from sqlalchemy import desc
import json
import requests

def send_courier_message():
    if not HAS_WEBSOCKET:
        print("websocket-client library not found. Falling back to HTTP API.")
        print("Install with: pip install websocket-client")
        send_via_http()
        return

    db = SessionLocal()
    try:
        # Find Odai (customer)
        customer = db.query(User).filter(User.name == "Odai").first()
        if not customer:
            print("Customer Odai not found")
            return

        print(f"Found customer: {customer.name} (ID: {customer.id})")

        # Find a conversation where Odai is the customer
        conversation = db.query(Conversation).filter(Conversation.customer_id == customer.id).first()
        if not conversation:
            print("No conversation found for Odai")
            return

        print(f"Found conversation ID: {conversation.id}")

        # Get the courier from the conversation
        courier = db.query(User).filter(User.id == conversation.courier_id).first()
        if not courier:
            print("Courier not found")
            return

        print(f"Sending message from courier: {courier.name} (ID: {courier.id})")

        # Get a valid token for the courier
        token_record = db.query(JWTToken).filter(
            JWTToken.user_id == courier.id,
            JWTToken.is_revoked == False
        ).order_by(desc(JWTToken.created_at)).first()
        if not token_record:
            print("No valid token found for courier. Please run create_courier_token.py first.")
            return

        token = token_record.access_token
        print("Using courier token for WebSocket connection")

        # Connect to WebSocket and send message
        ws_url = f"wss://971c-37-106-14-206.ngrok-free.app/ws/chat/{conversation.id}?token={token}"

        def on_message(ws, message):
            print(f"Received: {message}")
            # Parse the message and check if it's our sent message
            try:
                data = json.loads(message)
                if 'content' in data and data['content'] == "Hi abdulrahman":
                    print("Message successfully sent and received via WebSocket!")
                    ws.close()
            except:
                pass

        def on_error(ws, error):
            print(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            print("WebSocket connection closed")

        def on_open(ws):
            print("WebSocket connection opened")
            # Send the message
            message_data = {
                "content": "Hi abdulrahman",
                "message_type": "text"
            }
            ws.send(json.dumps(message_data))
            print("Message sent via WebSocket")

        # Create WebSocket connection
        ws = websocket.WebSocketApp(ws_url,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close,
                                  on_open=on_open)

        # Run the WebSocket
        ws.run_forever()

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

def send_via_http():
    db = SessionLocal()
    try:
        # Find Odai (customer)
        customer = db.query(User).filter(User.name == "Odai").first()
        if not customer:
            print("Customer Odai not found")
            return

        print(f"Found customer: {customer.name} (ID: {customer.id})")

        # Find a conversation where Odai is the customer
        conversation = db.query(Conversation).filter(Conversation.customer_id == customer.id).first()
        if not conversation:
            print("No conversation found for Odai")
            return

        print(f"Found conversation ID: {conversation.id}")

        # Get the courier from the conversation
        courier = db.query(User).filter(User.id == conversation.courier_id).first()
        if not courier:
            print("Courier not found")
            return

        print(f"Sending message from courier: {courier.name} (ID: {courier.id})")

        # Get a valid token for the courier
        token_record = db.query(JWTToken).filter(
            JWTToken.user_id == courier.id,
            JWTToken.is_revoked == False
        ).order_by(desc(JWTToken.created_at)).first()
        if not token_record:
            print("No valid token found for courier. Please run create_courier_token.py first.")
            return

        token = token_record.access_token
        print("Using courier token for HTTP API")

        # Use HTTP API to send message
        api_base_url = "https://971c-37-106-14-206.ngrok-free.app"
        url = f"{api_base_url}/chat/conversations/{conversation.id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "content": "Hi abdulrahman",
            "message_type": "text"
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            message_data = response.json()
            print(f"Message sent successfully via HTTP API! Message ID: {message_data['id']}")
            print("Note: HTTP API may not trigger real-time WebSocket broadcast - you might need to refresh the UI")
        else:
            print(f"Failed to send message via HTTP API. Status: {response.status_code}, Response: {response.text}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    send_courier_message()

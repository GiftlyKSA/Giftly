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
import random
import threading

# List of 10 random messages
messages = [
    "Hello! How can I help you today?",
    "Thank you for your order!",
    "Your package is on the way.",
    "Please confirm your delivery address.",
    "Is there anything else I can assist with?",
    "Great service from our team!",
    "We appreciate your business.",
    "Let me know if you have any questions.",
    "Your satisfaction is our priority.",
    "Have a wonderful day!"
]

def send_courier_message():
    if not HAS_WEBSOCKET:
        print("websocket-client library not found. Cannot send messages via WebSocket.")
        print("Install with: pip install websocket-client")
        return

    db = SessionLocal()
    try:
        # Find all conversations where courier_id == 5
        conversations = db.query(Conversation).filter(Conversation.courier_id == 5).all()
        if not conversations:
            print("No conversations found for courier_id 5")
            return

        # Get the courier
        courier = db.query(User).filter(User.id == 5).first()
        if not courier:
            print("Courier with id 5 not found")
            return

        print(f"Sending messages from courier: {courier.name} (ID: {courier.id})")

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

        threads = []
        for conversation in conversations:
            t = threading.Thread(target=send_to_conversation, args=(conversation, token))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

def send_to_conversation(conversation, token):
    random_message = random.choice(messages)
    ws_url = f"wss://971c-37-106-14-206.ngrok-free.app/ws/chat/{conversation.id}?token={token}"

    def on_message(ws, message):
        print(f"Received: {message}")
        # Parse the message and check if it's our sent message
        try:
            data = json.loads(message)
            if 'content' in data and data['content'] == random_message:
                print(f"Message successfully sent and received via WebSocket for conversation {conversation.id}!")
                ws.close()
        except:
            pass

    def on_error(ws, error):
        print(f"WebSocket error for conversation {conversation.id}: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"WebSocket connection closed for conversation {conversation.id}")

    def on_open(ws):
        print(f"WebSocket connection opened for conversation {conversation.id}")
        # Send the message
        message_data = {
            "content": random_message,
            "message_type": "text"
        }
        ws.send(json.dumps(message_data))
        print(f"Message sent via WebSocket to conversation {conversation.id}: '{random_message}'")

    # Create WebSocket connection
    ws = websocket.WebSocketApp(ws_url,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close,
                              on_open=on_open)

    # Run the WebSocket
    ws.run_forever()



if __name__ == "__main__":
    send_courier_message()

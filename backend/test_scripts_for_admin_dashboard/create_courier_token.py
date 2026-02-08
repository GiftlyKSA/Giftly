import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

from database import get_db_sync
from models import User
from auth import create_jwt_tokens

def create_courier_token():
    db_gen = get_db_sync()
    db = next(db_gen)
    try:
        # Find a courier user (preferably one assigned to Odai's order)
        # First, find Odai
        customer = db.query(User).filter(User.name == "Odai").first()

        courier = None
        if customer:
            # Find conversations where Odai is customer
            from models import Conversation
            conversation = db.query(Conversation).filter(Conversation.customer_id == customer.id).first()
            if conversation:
                # Get the courier from the conversation
                courier = db.query(User).filter(User.id == conversation.courier_id).first()

        if not courier:
            # Find any courier user
            courier = db.query(User).filter(User.role == "Courier").first()

        if not courier:
            print("No courier user found. Please create a courier user first.")
            return

        print(f"Found courier: {courier.name} (ID: {courier.id})")

        # Create JWT tokens for the courier
        access_token, refresh_token = create_jwt_tokens(db, courier)

        print(f"Created tokens for courier {courier.name}")
        print(f"Access Token: {access_token}")
        print(f"Refresh Token: {refresh_token}")
        print("\nYou can now run the send_courier_message.py script")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        try:
            next(db_gen)  # Close the session
        except StopIteration:
            pass

if __name__ == "__main__":
    create_courier_token()

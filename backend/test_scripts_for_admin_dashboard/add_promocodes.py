import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

import asyncio
from database import AsyncSessionLocal, engine, Base
from models import Promocode
from datetime import datetime, timedelta
from sqlalchemy import select

async def add_promocodes():
    async with AsyncSessionLocal() as db:
        try:
            # Define promocodes to create
            promocodes_data = [
                {
                    "name": "Welcome Discount",
                    "code": "WELCOME10",
                    "description": "10% off for new customers",
                    "percentage": 10,
                    "max_value": 5000,  # 50 SAR max discount
                    "minimum_order_value": 10000,  # Min 100 SAR order
                    "usage_limit": 100,
                    "valid_until": datetime.now() + timedelta(days=30),
                    "applicable_to": "order_total"
                },
                {
                    "name": "Flash Sale",
                    "code": "FLASH20",
                    "description": "20% off on all orders",
                    "percentage": 20,
                    "max_value": 10000,  # 100 SAR max discount
                    "minimum_order_value": 5000,  # Min 50 SAR order
                    "usage_limit": 50,
                    "valid_until": datetime.now() + timedelta(days=7),
                    "applicable_to": "order_total"
                },
                {
                    "name": "Loyalty Reward",
                    "code": "LOYALTY15",
                    "description": "15% off for loyal customers",
                    "percentage": 15,
                    "max_value": 7500,  # 75 SAR max discount
                    "minimum_order_value": 20000,  # Min 200 SAR order
                    "usage_limit": 200,
                    "valid_until": datetime.now() + timedelta(days=90),
                    "applicable_to": "order_total"
                },
                {
                    "name": "Holiday Special",
                    "code": "HOLIDAY25",
                    "description": "25% off during holiday season",
                    "percentage": 25,
                    "max_value": 15000,  # 150 SAR max discount
                    "minimum_order_value": 30000,  # Min 300 SAR order
                    "usage_limit": 500,
                    "valid_until": datetime.now() + timedelta(days=60),
                    "applicable_to": "order_total"
                },
                {
                    "name": "First Order",
                    "code": "FIRSTORDER",
                    "description": "Free delivery on first order",
                    "percentage": 100,
                    "max_value": 1500,  # 15 SAR max discount (typical delivery fee)
                    "minimum_order_value": 0,
                    "usage_limit": 1000,
                    "valid_until": datetime.now() + timedelta(days=365),
                    "applicable_to": "delivery_fee"
                }
            ]

            for promocode_data in promocodes_data:
                # Check if promocode already exists by code
                result = await db.execute(select(Promocode).where(Promocode.code == promocode_data["code"]))
                existing_promocode = result.scalar_one_or_none()
                if existing_promocode:
                    print(f"Promocode with code {promocode_data['code']} already exists")
                    continue

                # Create promocode
                promocode = Promocode(
                    name=promocode_data["name"],
                    code=promocode_data["code"],
                    description=promocode_data["description"],
                    percentage=promocode_data["percentage"],
                    max_value=promocode_data["max_value"],
                    minimum_order_value=promocode_data["minimum_order_value"],
                    usage_limit=promocode_data["usage_limit"],
                    valid_until=promocode_data["valid_until"],
                    applicable_to=promocode_data["applicable_to"],
                    active=True
                )
                db.add(promocode)
                print(f"Created promocode {promocode_data['code']} - {promocode_data['name']}")

            await db.commit()
            print("All promocodes created successfully")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(add_promocodes())
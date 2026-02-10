#!/usr/bin/env python3
import sys
import os
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

import asyncio
from database import AsyncSessionLocal
from models import Order, User, OrderStatus
from sqlalchemy import select, func

async def main():
    async with AsyncSessionLocal() as db:
        # Check total orders
        result = await db.execute(select(func.count()).select_from(Order))
        total_orders = result.scalar()
        print(f'Total orders: {total_orders}')

        # Check orders by status
        for status in OrderStatus:
            result = await db.execute(select(func.count()).select_from(Order).where(Order.status == status))
            count = result.scalar()
            print(f'{status.value}: {count}')

        # Check couriers
        result = await db.execute(select(User).where(User.role == 'Courier'))
        couriers = result.scalars().all()
        print(f'\nCouriers: {len(couriers)}')
        for courier in couriers:
            print(f'  - {courier.name} (ID: {courier.id}, City: {courier.city_id})')

            # Check orders assigned to this courier
            result = await db.execute(select(func.count()).select_from(Order).where(Order.assigned_to_user_id == courier.id))
            assigned_orders = result.scalar()
            print(f'    Assigned orders: {assigned_orders}')

            # Check available orders in courier's city
            if courier.city_id:
                result = await db.execute(select(func.count()).select_from(Order).where(
                    Order.status == OrderStatus.NEW,
                    Order.city_id == courier.city_id
                ))
                available_orders = result.scalar()
                print(f'    Available orders in city: {available_orders}')

if __name__ == "__main__":
    asyncio.run(main())

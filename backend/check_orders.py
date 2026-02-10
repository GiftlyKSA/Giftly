#!/usr/bin/env python3
import sys
import os
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

from database import get_db_sync
from models import Order, User, OrderStatus
from sqlalchemy.orm import Session

def main():
    db: Session = next(get_db_sync())

    try:
        # Check total orders
        total_orders = db.query(Order).count()
        print(f'Total orders: {total_orders}')

        # Check orders by status
        for status in OrderStatus:
            count = db.query(Order).filter(Order.status == status).count()
            print(f'{status.value}: {count}')

        # Check couriers
        couriers = db.query(User).filter(User.role == 'Courier').all()
        print(f'\nCouriers: {len(couriers)}')
        for courier in couriers:
            print(f'  - {courier.name} (ID: {courier.id}, City: {courier.city_id})')

            # Check orders assigned to this courier
            assigned_orders = db.query(Order).filter(Order.assigned_to_user_id == courier.id).count()
            print(f'    Assigned orders: {assigned_orders}')

            # Check available orders in courier's city
            if courier.city_id:
                available_orders = db.query(Order).filter(
                    Order.status == OrderStatus.NEW,
                    Order.city_id == courier.city_id
                ).count()
                print(f'    Available orders in city: {available_orders}')

    finally:
        db.close()

if __name__ == "__main__":
    main()
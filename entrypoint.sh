#!/bin/bash
# Wait for database or services if needed
# e.g., sleep 5 or use wait-for-it.sh

# Run your initialization scripts
python test_scripts_for_admin_dashboard/add_cities.py
python test_scripts_for_admin_dashboard/create_users.py
python test_scripts_for_admin_dashboard/check_and_create_admin.py
python test_scripts_for_admin_dashboard/add_reviews_table.py

# Start the FastAPI app
exec uvicorn main:app --host 0.0.0.0 --port 3000

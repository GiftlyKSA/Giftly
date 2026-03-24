import sys
import os
import asyncio
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)
os.chdir(backend_dir)

# This script is deprecated. Timezone is now stored in customer_profiles table.
# Use the following scripts instead:
# 1. create_customer_profiles_table.py
# 2. migrate_timezone_to_customer_profiles.py
# 3. drop_timezone_from_users.py

print("This script is deprecated. Timezone is now stored in customer_profiles table.")
print("Please use the following scripts in order:")
print("1. python test_scripts_for_admin_dashboard/create_customer_profiles_table.py")
print("2. python test_scripts_for_admin_dashboard/migrate_timezone_to_customer_profiles.py")
print("3. python test_scripts_for_admin_dashboard/drop_timezone_from_users.py")

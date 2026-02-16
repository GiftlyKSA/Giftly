import requests

# Host URL
HOST = "https://giftly-backend-tfjada.cranl.net"

# Phone number for testing (replace with actual phone number)
PHONE_NUMBER = "+966555555556"  # Example Saudi phone number (must start with 5)

def send_otp(phone_number):
    url = f"{HOST}/auth/send-otp"
    payload = {"phone_number": phone_number}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print("Send OTP Response:", data)
        return data.get("otp")
    else:
        print(f"Error sending OTP: {response.status_code} - {response.text}")
        return None

def verify_otp(phone_number, otp):
    url = f"{HOST}/auth/verify-otp"
    payload = {"phone_number": phone_number, "otp": otp}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print("Verify OTP Response:", data)
        return data.get("access_token")
    else:
        print(f"Error verifying OTP: {response.status_code} - {response.text}")
        return None

def get_me(access_token):
    url = f"{HOST}/auth/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print("User Details (/me endpoint):")
        for key, value in data.items():
            print(f"{key}: {value}")
        return data
    else:
        print(f"Error getting user details: {response.status_code} - {response.text}")
        return None

if __name__ == "__main__":
    # Step 1: Send OTP
    otp = send_otp(PHONE_NUMBER)
    if not otp:
        exit(1)

    # Step 2: Verify OTP
    access_token = verify_otp(PHONE_NUMBER, otp)
    if not access_token:
        exit(1)

    # Step 3: Get user details
    user_details = get_me(access_token)
    if user_details:
        print("\nScript completed successfully.")
    else:
        print("\nFailed to get user details.")
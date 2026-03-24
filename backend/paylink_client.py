import httpx
from typing import Dict, Any, Optional
import json


class PaylinkClient:
    """
    Python client for Paylink.sa API to create orders and invoices.
    """

    BASE_URL = "https://api.paylink.sa"

    def __init__(self, api_key: str, test_mode: bool = False):
        """
        Initialize the Paylink client.

        Args:
            api_key: Your Paylink API key
            test_mode: If True, use test environment (default: False)
        """
        self.api_key = api_key
        self.test_mode = test_mode
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30.0
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new order.

        Args:
            order_data: Order data dictionary containing:
                - amount: float (required)
                - currency: str (required, e.g., "SAR")
                - description: str (required)
                - customer: dict with name, email, phone (required)
                - orderNumber: str (optional)
                - callBackUrl: str (optional)
                - returnUrl: str (optional)

        Returns:
            Order response from Paylink API
        """
        endpoint = "/api/merchants/orders"
        response = await self.client.post(endpoint, json=order_data)
        response.raise_for_status()
        return response.json()

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new invoice.

        Args:
            invoice_data: Invoice data dictionary containing:
                - amount: float (required)
                - currency: str (required, e.g., "SAR")
                - description: str (required)
                - customer: dict with name, email, phone (required)
                - invoiceNumber: str (optional)
                - callBackUrl: str (optional)
                - returnUrl: str (optional)

        Returns:
            Invoice response from Paylink API
        """
        endpoint = "/api/merchants/invoices"
        response = await self.client.post(endpoint, json=invoice_data)
        response.raise_for_status()
        return response.json()

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order details by ID.

        Args:
            order_id: Order ID

        Returns:
            Order details
        """
        endpoint = f"/api/merchants/orders/{order_id}"
        response = await self.client.get(endpoint)
        response.raise_for_status()
        return response.json()

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Get invoice details by ID.

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice details
        """
        endpoint = f"/api/merchants/invoices/{invoice_id}"
        response = await self.client.get(endpoint)
        response.raise_for_status()
        return response.json()


# Example usage
async def example_usage():
    """
    Example of how to use the Paylink client.
    """
    api_key = "your-api-key-here"  # Replace with actual API key

    async with PaylinkClient(api_key) as client:
        # Create an order
        order_data = {
            "amount": 100.00,
            "currency": "SAR",
            "description": "Test Order",
            "customer": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "966501234567"
            },
            "orderNumber": "ORD-001",
            "callBackUrl": "https://yourwebsite.com/callback",
            "returnUrl": "https://yourwebsite.com/return"
        }

        try:
            order_response = await client.create_order(order_data)
            print("Order created:", json.dumps(order_response, indent=2))
        except httpx.HTTPStatusError as e:
            print(f"Error creating order: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Unexpected error: {e}")

        # Create an invoice
        invoice_data = {
            "amount": 50.00,
            "currency": "SAR",
            "description": "Test Invoice",
            "customer": {
                "name": "Jane Smith",
                "email": "jane@example.com",
                "phone": "966509876543"
            },
            "invoiceNumber": "INV-001",
            "callBackUrl": "https://yourwebsite.com/callback",
            "returnUrl": "https://yourwebsite.com/return"
        }

        try:
            invoice_response = await client.create_invoice(invoice_data)
            print("Invoice created:", json.dumps(invoice_response, indent=2))
        except httpx.HTTPStatusError as e:
            print(f"Error creating invoice: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Unexpected error: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
"""
Paylink.sa API client.

Auth: POST /api/auth with apiId + secretKey → id_token (Bearer).
Token is valid for 30 h (persistToken=true) or 30 min (persistToken=false).
The client caches the token and refreshes it on 401.
"""

import time
from typing import Any, Dict, Optional

import httpx


class PaylinkClient:
    BASE_URL = "https://api.paylink.sa"

    def __init__(
        self,
        api_key: str,
        test_mode: bool = False,
        api_id: str = "",
    ):
        """
        Args:
            api_key:  secretKey (or legacy X-API-KEY if api_id is empty)
            test_mode: passed to Paylink test environment flag
            api_id:   apiId — when provided, uses Bearer-token auth
        """
        self._api_key = api_key
        self._api_id = api_id
        self._test_mode = test_mode
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "PaylinkClient":
        self._client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=30.0)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def _get_token(self) -> str:
        """Return a valid Bearer token, refreshing if expired."""
        if self._token and time.time() < self._token_expiry:
            return self._token
        resp = await self._client.post(
            "/api/auth",
            json={"apiId": self._api_id, "secretKey": self._api_key, "persistToken": True},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["id_token"]
        # persistToken=True → 30 h; subtract 5 min buffer
        self._token_expiry = time.time() + 30 * 3600 - 300
        return self._token

    async def _headers(self) -> Dict[str, str]:
        if self._api_id:
            token = await self._get_token()
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        return {"X-API-KEY": self._api_key, "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = await self._headers()
        resp = await self._client.post(endpoint, json=payload, headers=headers)
        if resp.status_code == 401 and self._api_id:
            # Token may have expired early — force refresh once
            self._token = None
            headers = await self._headers()
            resp = await self._client.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def _get(self, endpoint: str) -> Dict[str, Any]:
        headers = await self._headers()
        resp = await self._client.get(endpoint, headers=headers)
        if resp.status_code == 401 and self._api_id:
            self._token = None
            headers = await self._headers()
            resp = await self._client.get(endpoint, headers=headers)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Paylink payment invoice.

        Required keys: amount (SAR float), currency, description,
        customer (name/email/phone), invoiceNumber, callBackUrl, returnUrl.
        """
        return await self._post("/api/merchants/invoices", invoice_data)

    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Paylink order (alternative to invoice)."""
        return await self._post("/api/merchants/orders", order_data)

    async def get_invoice(self, transaction_no: str) -> Dict[str, Any]:
        """Fetch invoice/transaction status by Paylink transactionNo."""
        return await self._get(f"/api/merchants/invoices/{transaction_no}")

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """Fetch order status by Paylink order ID."""
        return await self._get(f"/api/merchants/orders/{order_id}")

    async def cancel_invoice(self, transaction_no: str) -> Dict[str, Any]:
        """Cancel a pending Paylink invoice."""
        return await self._post(
            f"/api/merchants/invoices/{transaction_no}/cancel", {}
        )

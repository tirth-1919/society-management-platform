"Database and malformed-input HTTP 500 regression checks."""
from __future__ import annotations
import pytest
SAFE_GETS = [
    "/api/buildings?society_id=not-an-integer",
    "/api/flats?society_id=not-an-integer",
    "/api/flats?society_id=1&block_id=not-an-integer",
    "/api/v1/search?limit=not-an-integer",
    "/api/v1/automation/history?limit=not-an-integer",
    "/registration-status/999",
    "/resident/bills/999",
    "/resident/bills/999/pdf",
    "/resident/receipts/999/qr",
    "/resident/support/999",
    "/resident/documents/999/download",
    "/payments/success/999",
    "/payments/failed/999",
    "/payments/cancelled/999",
    "/payments/retry/999",
    "/payments/receipt/999",
    "/payments/refund/999",
    "/payments/multi-month/999",
    "/admin/registrations/999",
    "/admin/residents/999/detail",
    "/admin/residents/999/profile",
    "/accounting/resident-ledger/999",
    "/complaints/999",
    "/documents/download/999",
]

@pytest.mark.parametrize("path", SAFE_GETS)
def test_missing_records_and_malformed_inputs_never_return_500(app, client, path):
    response = client.get(path, follow_redirects=False)
    print(f"{path:70} {response.status_code}")
    assert response.status_code != 500, f"Safe edge-case URL returned HTTP 500: {path}"

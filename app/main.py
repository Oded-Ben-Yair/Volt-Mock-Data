from __future__ import annotations

"""
Fresh, self‑contained FastAPI backend for the Volt / Retell voice‑agent demo.

Key points
-----------
* **No external dataset required at boot** – if the JSON file isn’t present, we fall back to an in‑memory stub so Render never 500s on start‑up.
* **Environment‑override** – set `DATA_FILE=/full/path/to/retell_mock_full_dataset.json` if you later mount the big mock file.
* **Endpoints & schemas** match the six Function‑Nodes already wired in Retell (`check_order_status`, `cancel_order`, `request_refund`, `create_ticket`, `log_call`, `get_current_datetime`).
* **All responses are small, flat JSON** – nothing Retell’s LLM can’t digest.

Run locally:
```
poetry install  # or pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Deploy on Render: keep the Start Command `uvicorn main:app --host 0.0.0.0 --port 8000`.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
DATA_PATH = Path(os.getenv("DATA_FILE", APP_DIR / "retell_mock_full_dataset.json"))

def _load_data() -> dict:
    """Load the big mock dataset if it exists, otherwise return a minimal stub."""
    if DATA_PATH.exists():
        try:
            with DATA_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            # Log and continue with stub so container still boots
            print("⚠️  Failed to parse JSON dataset:", exc)
    # Fallback stub keeps the API alive
    return {"orders": [], "users": [], "products": []}

# In‑memory "DB" (good enough for a demo)
db = _load_data()

app = FastAPI(title="Volt Voice‑Agent Mock Backend", version="1.0.0")

# ───────────────────────────────────────────────────────────── Schemas ──

class OrderStatusRequest(BaseModel):
    order_id: str = Field(..., example="A2928")

class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    delivery_eta: Optional[str] = None

class CancelOrderRequest(BaseModel):
    order_id: str

class CancelOrderResponse(BaseModel):
    success: bool
    note: str

class RefundRequest(BaseModel):
    order_id: str
    reason: str

class RefundResponse(BaseModel):
    approved: bool
    refund_amount: float | None = None
    note: str

class TicketRequest(BaseModel):
    issue_type: str
    user_notes: str
    order_id: Optional[str] = None

class TicketResponse(BaseModel):
    ticket_id: str
    message: str

class LogCallRequest(BaseModel):
    call_summary: str
    sentiment: str | None = None
    timestamp: Optional[str] = None  # ISO‑8601 string so we avoid TZ headaches

class LogCallResponse(BaseModel):
    stored: bool

class DateTimeResponse(BaseModel):
    date: str  # YYYY‑MM‑DD
    time: str  # HH:MM (24h)

# ─────────────────────────────────────────────────────────── Helpers ──

def _find_order(order_id: str) -> dict | None:
    return next((o for o in db["orders"] if o["order_id"] == order_id), None)

# ─────────────────────────────────────────────────────────── Routes ──

@app.post("/check_order_status", response_model=OrderStatusResponse)
async def check_order_status(payload: OrderStatusRequest):
    order = _find_order(payload.order_id)
    if not order:
        raise HTTPException(404, "order_not_found")
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "delivery_eta": order.get("delivery_eta"),
    }

@app.post("/cancel_order", response_model=CancelOrderResponse)
async def cancel_order(payload: CancelOrderRequest):
    order = _find_order(payload.order_id)
    if not order:
        raise HTTPException(404, "order_not_found")
    if not order.get("can_cancel", False):
        return {"success": False, "note": "Order can no longer be cancelled."}
    order["status"] = "cancelled"
    order["can_cancel"] = False
    return {"success": True, "note": "Order cancelled successfully."}

@app.post("/request_refund", response_model=RefundResponse)
async def request_refund(payload: RefundRequest):
    order = _find_order(payload.order_id)
    if not order:
        raise HTTPException(404, "order_not_found")
    if not order.get("eligible_for_refund", False):
        return {
            "approved": False,
            "note": "Order is not eligible for refund (outside policy window).",
        }
    # naive refund calc:  full refund of all items’ price (if price available)
    refund_amount = 0.0
    for item in order.get("items", []):
        # Price lookup optional
        refund_amount += 5.0 * item.get("qty", 1)  # flat 5 per item demo
    order["eligible_for_refund"] = False
    return {
        "approved": True,
        "refund_amount": round(refund_amount, 2),
        "note": "Refund approved and will be processed within 3‑5 days.",
    }

@app.post("/create_ticket", response_model=TicketResponse)
async def create_ticket(payload: TicketRequest):
    ticket_id = f"volt-{int(datetime.now().timestamp())}"
    # For demo we don’t persist; you could append to db["tickets"]
    return {"ticket_id": ticket_id, "message": "Ticket created. Our team will follow‑up."}

@app.post("/log_call", response_model=LogCallResponse)
async def log_call(payload: LogCallRequest):
    # In a real system we’d push to a DB or analytics pipeline. Here we just ACK.
    return {"stored": True}

@app.post("/get_current_datetime", response_model=DateTimeResponse)
async def get_current_datetime():
    now = datetime.now(timezone.utc).astimezone()
    return {"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M")}

# ────────────────────────────────────────────────────────────── Health ──

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)


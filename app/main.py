"""
app/main.py
FastAPI mock backend for Retell Voice-Agent – **v1.1 / 2025-04-23**

Changelog
---------
* v1.1 – ADD: `end_call()` function  ✅
        – UPDATE: `SYSTEM_PROMPT` now lists end_call and explains when to use it
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# 📦  DATA LOADER
# --------------------------------------------------------------------------- #

DATA_FILE = pathlib.Path(__file__).with_name("retell_mock_full_dataset.json")

def load_data() -> dict:
    try:
        with DATA_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"❌ {DATA_FILE.name} not found – make sure it’s in app/")

DATA = load_data()
ORDERS = {o["order_id"]: o for o in DATA["orders"]}

# --------------------------------------------------------------------------- #
# 🚀  FASTAPI
# --------------------------------------------------------------------------- #

app = FastAPI(title="Volt AI Mock Backend", version="1.1")

class OrderID(BaseModel):
    order_id: str = Field(..., examples=["A7872"])

class RefundRequest(OrderID):
    reason: str = Field(..., examples=["missing item", "spoiled"])

class TicketRequest(BaseModel):
    issue_type: str = Field(..., examples=["escalation", "complaint"])
    user_notes: str

class LogCall(BaseModel):
    call_summary: str
    sentiment: str = Field(..., examples=["positive", "neutral", "negative"])
    timestamp: str

# ------------------------------  API ROUTES  ------------------------------- #

@app.get("/health")
def health():
    return {"status": "ok", "dataset_rows": len(ORDERS)}

@app.post("/check_order_status")
def check_order_status(payload: OrderID):
    order = ORDERS.get(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {payload.order_id} not found")
    return order

@app.post("/cancel_order")
def cancel_order(payload: OrderID):
    order = ORDERS.get(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order["can_cancel"]:
        return {"success": False, "note": "Order can no longer be cancelled"}
    order["status"] = "cancelled"
    order["can_cancel"] = False
    return {"success": True, "note": "Order cancelled successfully"}

@app.post("/request_refund")
def request_refund(payload: RefundRequest):
    order = ORDERS.get(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order["eligible_for_refund"]:
        return {"approved": False, "reason": "Refund window expired or not eligible"}
    return {"approved": True, "refund_amount": 25.00, "reason_ack": payload.reason}

@app.post("/create_ticket")
def create_ticket(payload: TicketRequest):
    ticket_id = f"volt-{int(datetime.utcnow().timestamp())}"
    return {"ticket_id": ticket_id, "message": "Ticket created – a human will reach out shortly"}

@app.post("/get_current_datetime")
def get_current_datetime():
    now = datetime.now(timezone.utc)
    return {"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S")}

@app.post("/log_call")
def log_call(payload: LogCall):
    # In prod you’d push to BigQuery / Slack etc.
    return {"stored": True, "received": payload.dict()}

# ----------  NEW: end_call  ---------- #

@app.post("/end_call")
def end_call():
    """
    Cleanly terminates the session.
    In a live system this could:
      * Close Twilio media streams
      * Persist final analytics
      * Trigger post-call surveys
    Here we just return ok=True.
    """
    return {"ok": True, "goodbye": "Call ended – have a great day!"}

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid, json, os

app = FastAPI(title="Volt Mock Support API", version="1.0.0")

# ------------------------------------------------------------------
# 0️⃣  Load mock data (orders / users / products) -------------------
# ------------------------------------------------------------------
DATA_PATH = os.getenv("VOLT_DATA_PATH", "retell_mock_full_dataset.json")

def _load_data() -> Dict[str, Any]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

db = _load_data()

def _get_order(order_id: str) -> Optional[Dict[str, Any]]:
    return next((o for o in db["orders"] if o["order_id"] == order_id), None)

# ------------------------------------------------------------------
# 1️⃣  Pydantic request / response models ---------------------------
# ------------------------------------------------------------------
class OrderId(BaseModel):
    order_id: str = Field(..., example="A1234")

class RefundPayload(OrderId):
    reason: str = Field(..., example="missing_item")

class TicketPayload(BaseModel):
    issue_type: str = Field(..., example="delivery_issue")
    user_notes: str
    order_id: Optional[str] = None

class CallLog(BaseModel):
    call_summary: str
    sentiment: Optional[str] = "neutral"
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())

# ------------------------------------------------------------------
# 2️⃣  Endpoints Retell.ai will call --------------------------------
# ------------------------------------------------------------------
@app.post("/check_order_status")
def check_order_status(body: OrderId):
    order = _get_order(body.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "delivery_eta": order["delivery_eta"],
        "delivered_at": order["delivered_at"],
    }

@app.post("/cancel_order")
def cancel_order(body: OrderId):
    order = _get_order(body.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if not order["can_cancel"]:
        return {"success": False, "note": "Order can no longer be canceled."}
    order["status"], order["can_cancel"] = "cancelled", False
    return {"success": True, "note": "Order canceled successfully."}

@app.post("/request_refund")
def request_refund(body: RefundPayload):
    order = _get_order(body.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if not order["eligible_for_refund"]:
        return {"approved": False, "refund_amount": 0.0, "message": "Order not eligible for refund."}
    refund_amount = round(sum(i["qty"] * 5 for i in order["items"]), 2)   # quick mock calc
    order["eligible_for_refund"] = False
    return {"approved": True, "refund_amount": refund_amount, "message": f"Refund ${refund_amount} approved."}

@app.post("/create_ticket")
def create_ticket(body: TicketPayload):
    ticket_id = f"volt-{uuid.uuid4().hex[:8]}"
    return {"ticket_id": ticket_id, "message": "Support ticket created."}

@app.post("/log_call")
def log_call(body: CallLog):
    # In production you'd persist this somewhere; for now we just print
    print("CALL-LOG:", body.json())
    return {"stored": True}

@app.post("/get_current_datetime")
def get_current_datetime():
    now = datetime.utcnow()
    return {"date": now.strftime('%Y-%m-%d'), "time": now.strftime('%H:%M:%S')}


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json, datetime, os

DATA_FILE = os.getenv("DATA_FILE", "retell_mock_full_dataset.json")

# ----------  Helpers ----------
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    orders = {o["order_id"]: o for o in data["orders"]}
    return data, orders

DATA, ORDERS = load_data()
print(f"✅  loaded {len(ORDERS)} orders")

def ok(data: Dict[str, Any]):          # standard 200 wrapper
    return data

def not_found(order_id: str):
    raise HTTPException(status_code=404,
                        detail=f"Order {order_id} not found")

def extract_args(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retell always sends: {"args": {...}}
    """
    if "args" not in body or not isinstance(body["args"], dict):
        raise HTTPException(400, detail="Payload must contain 'args' object")
    return body["args"]

# ----------  FastAPI ----------
app = FastAPI()

@app.get("/")
async def health():
    return ok({"status": "ok", "ts": datetime.datetime.utcnow().isoformat()})

# 1) check_order_status --------------------------------------------------------
@app.post("/check_order_status")
async def check_order_status(body: Dict[str, Any]):
    args = extract_args(body)
    order_id = args.get("order_id")
    order = ORDERS.get(order_id)
    if not order:
        not_found(order_id)

    return ok({
        "order_id": order_id,
        "status": order["status"],
        "delivery_eta": order.get("delivery_eta"),
        "delivered_at": order.get("delivered_at")
    })

# 2) cancel_order --------------------------------------------------------------
@app.post("/cancel_order")
async def cancel_order(body: Dict[str, Any]):
    args = extract_args(body)
    order_id = args.get("order_id")
    order = ORDERS.get(order_id) or not_found(order_id)

    if not order["can_cancel"]:
        raise HTTPException(400, detail="Order can no longer be cancelled")

    order["status"] = "cancelled"
    order["can_cancel"] = False
    return ok({"order_id": order_id, "cancelled": True})

# 3) request_refund ------------------------------------------------------------
@app.post("/request_refund")
async def request_refund(body: Dict[str, Any]):
    args = extract_args(body)
    order_id = args.get("order_id")
    reason   = args.get("reason")
    order = ORDERS.get(order_id) or not_found(order_id)

    if not order["eligible_for_refund"]:
        raise HTTPException(400,
            detail=f"Order {order_id} is not eligible for refund")
    order["eligible_for_refund"] = False
    return ok({"order_id": order_id,
               "approved": True,
               "reason": reason})

# 4) create_ticket -------------------------------------------------------------
@app.post("/create_ticket")
async def create_ticket(body: Dict[str, Any]):
    args = extract_args(body)
    ticket_id = f"volt-{abs(hash(str(datetime.datetime.utcnow())))%10**10}"
    return ok({ "ticket_id": ticket_id,
                "issue_type": args.get("issue_type"),
                "order_id":   args.get("order_id"),
                "notes_saved": True })

# 5) log_call ------------------------------------------------------------------
@app.post("/log_call")
async def log_call(body: Dict[str, Any]):
    args = extract_args(body)
    # Here you’d push to Slack / DB – we just print to logs
    print("📝 LOG_CALL", args)
    return ok({"stored": True})

# 6) get_current_datetime ------------------------------------------------------
@app.post("/get_current_datetime")
async def get_current_datetime(_: Dict[str, Any]):
    now = datetime.datetime.utcnow()
    return ok({"date": now.strftime("%Y-%m-%d"),
               "time": now.strftime("%H:%M:%S")})


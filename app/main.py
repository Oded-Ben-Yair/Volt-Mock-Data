
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    with open("retell_mock_full_dataset.json", "r") as f:
        mock_data = json.load(f)
except FileNotFoundError:
    mock_data = {"orders": []}
    print("⚠️ WARNING: Mock dataset not found. Using empty dataset.")

orders = mock_data["orders"]

@app.post("/check_order_status")
async def check_order_status(req: Request):
    body = await req.json()
    order_id = body.get("order_id")
    for order in orders:
        if order["order_id"] == order_id:
            return {
                "status": order["status"],
                "vendor_name": order["vendor_name"],
                "eta": order["delivery_eta"]
            }
    return {"detail": "Order not found"}, 404

@app.post("/cancel_order")
async def cancel_order(req: Request):
    body = await req.json()
    order_id = body.get("order_id")
    for order in orders:
        if order["order_id"] == order_id:
            if order.get("can_cancel"):
                return {"message": f"Order {order_id} has been canceled successfully."}
            else:
                return {"message": f"Order {order_id} can no longer be canceled."}
    return {"detail": "Order not found"}, 404

@app.post("/request_refund")
async def request_refund(req: Request):
    body = await req.json()
    order_id = body.get("order_id")
    reason = body.get("reason", "").lower()
    for order in orders:
        if order["order_id"] == order_id:
            if order.get("eligible_for_refund"):
                return {"message": f"Refund for order {order_id} has been processed for reason: {reason}."}
            else:
                return {"message": f"Order {order_id} is not eligible for a refund based on current policy."}
    return {"detail": "Order not found"}, 404

@app.post("/create_ticket")
async def create_ticket(req: Request):
    body = await req.json()
    issue_type = body.get("issue_type")
    user_notes = body.get("user_notes")
    order_id = body.get("order_id", "unknown")
    return {
        "message": "Ticket has been created.",
        "ticket": {
            "issue_type": issue_type,
            "order_id": order_id,
            "notes": user_notes
        }
    }

@app.post("/get_current_datetime")
async def get_current_datetime():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"datetime": now}

@app.post("/log_call")
async def log_call(req: Request):
    body = await req.json()
    return {"message": "Call log recorded", "data": body}

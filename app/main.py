# app/main.py
"""
Volt Mock API for Retell voice-agent tests
— improved version —
* Handles Render's X-Forwarded-Prefix automatically (root_path="")
* Fails fast if the dataset is missing
* Adds a health-check endpoint and structured logging
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from pathlib import Path
import logging
import json
import os

# ---------------------------------------------------------------------
#  Logging
# ---------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ---------------------------------------------------------------------
#  FastAPI setup
#   • root_path="" forces the same paths locally and on Render
# ---------------------------------------------------------------------
app = FastAPI(root_path=os.getenv("ROOT_PATH", ""))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
#  Load mock-data JSON
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent          # …/app
DATA_FILE = BASE_DIR / "retell_mock_full_dataset.json"

try:
    with DATA_FILE.open("r", encoding="utf-8") as fh:
        mock_data = json.load(fh)
    logging.info("✅  loaded %s orders from %s", len(mock_data["orders"]), DATA_FILE.name)
except FileNotFoundError as exc:
    logging.critical("❌  %s not found – aborting deploy", DATA_FILE)
    raise RuntimeError(
        "retell_mock_full_dataset.json is missing – container cannot serve data"
    ) from exc

orders = mock_data["orders"]

# ---------------------------------------------------------------------
#  Health-check endpoint  -> Render looks for 200 on “/”
# ---------------------------------------------------------------------
@app.get("/")
async def ping():
    return {"status": "ok", "ts": datetime.utcnow().isoformat() + "Z"}


# ---------------------------------------------------------------------
#  Business endpoints
# ---------------------------------------------------------------------
@app.post("/check_order_status")
async def check_order_status(req: Request):
    body = await req.json()
    order_id = body.get("order_id")
    order = next((o for o in orders if o["order_id"] == order_id), None)

    if order:
        return {
            "status": order["status"],
            "vendor_name": order["vendor_name"],
            "eta": order["delivery_eta"],
        }

    # 200 + custom payload → LLM can respond gracefully
    return {"status": "not_found", "detail": f"Order {order_id} not found"}

# ---------------------------------------------------------------------
@app.post("/cancel_order")
async def cancel_order(req: Request):
    body = await req.json()
    order_id = body.get("order_id")
    order = next((o for o in orders if o["order_id"] == order_id), None)

    if not order:
        return {"status": "not_found", "detail": f"Order {order_id} not found"}

    if order.get("can_cancel"):
        order["status"] = "cancelled"
        return {"message": f"Order {order_id} has been cancelled successfully."}

    return {"message": f"Order {order_id} can no longer be cancelled."}

# ---------------------------------------------------------------------
@app.post("/request_refund")
async def request_refund(req: Request):
    body = await req.json()
    order_id = body.get("order_id")
    reason = body.get("reason", "").lower()
    order = next((o for o in orders if o["order_id"] == order_id), None)

    if not order:
        return {"status": "not_found", "detail": f"Order {order_id} not found"}

    if order.get("eligible_for_refund"):
        return {
            "message": f"Refund for order {order_id} has been processed.",
            "reason": reason,
        }

    return {"message": f"Order {order_id} is not eligible for a refund."}

# ---------------------------------------------------------------------
@app.post("/create_ticket")
async def create_ticket(req: Request):
    body = await req.json()
    ticket = {
        "issue_type": body.get("issue_type"),
        "order_id": body.get("order_id", "unknown"),
        "notes": body.get("user_notes"),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    return {"message": "Ticket has been created.", "ticket": ticket}

# ---------------------------------------------------------------------
@app.post("/get_current_datetime")
async def get_current_datetime():
    now = datetime.utcnow().strftime("%Y-m-d %H:%M:%S")
    return {"datetime": now}

# ---------------------------------------------------------------------
@app.post("/log_call")
async def log_call(req: Request):
    body = await req.json()
    logging.info("📞  call log: %s", body)
    return {"message": "Call log recorded", "data": body}


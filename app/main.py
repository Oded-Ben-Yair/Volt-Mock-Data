"""
Volt Mock API – Render-ready
────────────────────────────
* Auto-detects Reverse-Proxy root_path (X-Forwarded-Prefix)
* Loads mock dataset once and fails fast if file missing
* Accepts both:
    ① {"order_id": "..."}  – manual cURL
    ② {"args": {"order_id": "..."}}  – Retell Function Nodes
* Health-check endpoint  GET /
* Structured logging
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from pathlib import Path
import logging
import json
import os

# ───────────────────────── Logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("volt-mock")

# ───────────────────────── Data Load
DATA_PATH = Path(__file__).parent / "retell_mock_full_dataset.json"
if not DATA_PATH.exists():
    log.error("❌  mock dataset %s not found – aborting startup", DATA_PATH)
    raise FileNotFoundError(DATA_PATH)

with DATA_PATH.open() as f:
    orders = json.load(f)

log.info("✅  loaded %s orders from %s", len(orders), DATA_PATH.name)

# ───────────────────────── FastAPI app
app = FastAPI(root_path=os.getenv("ROOT_PATH", ""))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────── Helpers
def _get(param: str, body: dict, required: bool = True):
    """Return param from body or body['args'] wrapper."""
    val = body.get(param)
    if val is None and isinstance(body.get("args"), dict):
        val = body["args"].get(param)
    if required and val in (None, ""):
        raise HTTPException(status_code=422, detail=f"Missing parameter: {param}")
    return val


# ───────────────────────── Endpoints
@app.get("/")
async def health():
    """Simple health-check."""
    return {"status": "ok", "ts": datetime.utcnow().isoformat() + "Z"}


@app.post("/check_order_status")
async def check_order_status(req: Request):
    body = await req.json()
    order_id = _get("order_id", body)

    for order in orders:
        if order["order_id"] == order_id:
            return {
                "status": order["status"],
                "vendor_name": order["vendor_name"],
                "eta": order["delivery_eta"],
            }

    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@app.post("/cancel_order")
async def cancel_order(req: Request):
    body = await req.json()
    order_id = _get("order_id", body)

    for order in orders:
        if order["order_id"] == order_id:
            if order.get("can_cancel"):
                return {"success": True, "message": f"Order {order_id} canceled."}
            return {"success": False, "message": f"Order {order_id} can no longer be canceled."}

    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@app.post("/request_refund")
async def request_refund(req: Request):
    body = await req.json()
    order_id = _get("order_id", body)
    reason   = _get("reason", body)

    for order in orders:
        if order["order_id"] == order_id:
            if order.get("eligible_for_refund"):
                return {
                    "approved": True,
                    "refund_amount": order.get("refund_amount", 0),
                    "reason_ack": reason,
                }
            return {"approved": False, "message": f"Order {order_id} is not eligible for a refund"}

    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@app.post("/create_ticket")
async def create_ticket(req: Request):
    body       = await req.json()
    issue_type = _get("issue_type", body)
    user_notes = _get("user_notes", body)
    order_id   = _get("order_id", body, required=False)

    ticket_id = f"volt-{datetime.utcnow().timestamp():.0f}"
    return {
        "ticket_id": ticket_id,
        "issue_type": issue_type,
        "order_id": order_id,
        "notes_saved": bool(user_notes),
    }


@app.post("/log_call")
async def log_call(req: Request):
    body         = await req.json()
    call_summary = _get("call_summary", body)
    sentiment    = _get("sentiment", body)
    timestamp    = _get("timestamp", body)

    log.info("📝 LOG_CALL | %s | %s", sentiment, call_summary[:80])
    return {"stored": True}


@app.post("/get_current_datetime")
async def get_current_datetime():
    now = datetime.now(timezone.utc)
    return {"date": now.date().isoformat(), "time": now.time().isoformat(timespec="seconds")}


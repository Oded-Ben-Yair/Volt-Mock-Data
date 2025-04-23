"""Volt Mock API – Render-ready v2 (dict-based, KeyError-proof)"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from pathlib import Path
import logging, json, os

logging.basicConfig(level="INFO",
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("volt-mock")

# ───── dataset ────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "retell_mock_full_dataset.json"
if not DATA_PATH.exists():
    raise FileNotFoundError(DATA_PATH)

with DATA_PATH.open() as f:
    raw = json.load(f)

if isinstance(raw, list):
    orders_by_id = {o["order_id"]: o for o in raw}
elif isinstance(raw, dict):
    orders_by_id = raw
else:
    raise TypeError("Unsupported dataset format")

log.info("✅  loaded %s orders", len(orders_by_id))

# ───── app & CORS ─────────────────────────────────────────────────────────
app = FastAPI(root_path=os.getenv("ROOT_PATH", ""))
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

def _arg(body: dict, key: str, required=True):
    val = body.get(key) or body.get("args", {}).get(key)
    if required and not val:
        raise HTTPException(422, f"Missing parameter: {key}")
    return val

@app.get("/")
async def health():  # render health-check
    return {"status": "ok", "ts": datetime.utcnow().isoformat() + "Z"}

@app.post("/check_order_status")
async def check_order_status(req: Request):
    body      = await req.json()
    order_id  = _arg(body, "order_id")
    order     = orders_by_id.get(order_id)
    if not order:
        raise HTTPException(404, f"Order {order_id} not found")

    return {
        "status":      order.get("status", "unknown"),
        "vendor_name": order.get("vendor_name", "Volt"),
        "eta":         order.get("delivery_eta") or order.get("eta")
    }

@app.post("/cancel_order")
async def cancel_order(req: Request):
    body     = await req.json()
    order_id = _arg(body, "order_id")
    order    = orders_by_id.get(order_id)
    if not order:
        raise HTTPException(404, f"Order {order_id} not found")
    if order.get("can_cancel"):
        order["status"] = "canceled"
        return {"success": True, "message": f"Order {order_id} canceled."}
    return {"success": False, "message": f"Order {order_id} can no longer be canceled."}

@app.post("/request_refund")
async def request_refund(req: Request):
    body      = await req.json()
    order_id  = _arg(body, "order_id")
    reason    = _arg(body, "reason")
    order     = orders_by_id.get(order_id)
    if not order:
        raise HTTPException(404, f"Order {order_id} not found")
    if order.get("eligible_for_refund"):
        return {"approved": True, "refund_amount": order.get("refund_amount", 0),
                "reason_ack": reason}
    return {"approved": False, "message": "Order not eligible for refund"}

@app.post("/create_ticket")
async def create_ticket(req: Request):
    body       = await req.json()
    issue_type = _arg(body, "issue_type")
    user_notes = _arg(body, "user_notes")
    order_id   = _arg(body, "order_id", required=False)
    tid        = f"volt-{int(datetime.utcnow().timestamp())}"
    return {"ticket_id": tid, "issue_type": issue_type,
            "order_id": order_id, "notes_saved": bool(user_notes)}

@app.post("/log_call")
async def log_call(req: Request):
    body = await req.json()
    log.info("📝 LOG_CALL %s", {k: body.get(k) or body.get('args', {}).get(k) for k in body})
    return {"stored": True}

@app.post("/get_current_datetime")
async def get_current_datetime():
    now = datetime.now(timezone.utc)
    return {"date": now.date().isoformat(), "time": now.time().isoformat(timespec="seconds")}

